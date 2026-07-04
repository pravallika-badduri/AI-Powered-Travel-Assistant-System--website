from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
import requests
import json
from math import radians, sin, cos, sqrt, atan2
from collections import defaultdict, deque

# ---------------- Gemini API ----------------
API_KEY = 'AIzaSyD0QBoMd4P_bGRqk1JNsVfxYqCdZtXQYs0'
API_URL = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}'

# ---------------- Home Page ----------------
def home_view(request):
    return render(request, 'smart_traverser/home.html')

# ----------------- Graph-based Routing -----------------
def build_graph(routes):
    graph = defaultdict(list)
    for (src, dst), stops in routes.items():
        all_nodes = [src] + stops + [dst]
        for i in range(len(all_nodes) - 1):
            u, v = all_nodes[i].lower(), all_nodes[i + 1].lower()
            graph[u].append(v)
            graph[v].append(u)
    return graph

def find_path(graph, start, end):
    start, end = start.lower(), end.lower()
    queue = deque([[start]])
    visited = set()
    while queue:
        path = queue.popleft()
        node = path[-1]
        if node == end:
            return path
        if node not in visited:
            visited.add(node)
            for neighbor in graph[node]:
                if neighbor not in visited:
                    queue.append(path + [neighbor])
    return None

@csrf_exempt
def get_response(request):
    if request.method == 'POST':
        message = request.POST.get('message', '').lower().strip()

        if message == "stop":
            return JsonResponse({'response': "Voice assistant stopped."})

        stage = request.session.get('chat_stage', 'initial')

        if stage == 'initial':
            if 'distance' in request.session and 'costs' in request.session:
                source = request.session.get('source', '').title()
                destination = request.session.get('destination', '').title()
                distance = request.session.get('distance')
                costs = request.session.get('costs')
                low_meal = request.session.get('low_meal', {})
                med_meal = request.session.get('med_meal', {})
                high_meal = request.session.get('high_meal', {})

                low_food = ', '.join([f"{item} ₹{cost}" for item, cost in low_meal.items()])
                med_food = ', '.join([f"{item} ₹{cost}" for item, cost in med_meal.items()])
                high_food = ', '.join([f"{item} ₹{cost}" for item, cost in high_meal.items()])

                response = (
                    f"The distance between {source} and {destination} is {distance} kilometers.\n"
                    f"Travel costs: Bus ₹{costs['bus']}, Train ₹{costs['train']}, Flight ₹{costs['flight']}.\n"
                    f"\nLow Budget Food: {low_food}\n"
                    f"Medium Budget Food: {med_food}\n"
                    f"High Budget Food: {high_food}\n"
                    f"\nWould you like to book a ticket or ask any questions?"
                )
                request.session['chat_stage'] = 'ask_action'
                return JsonResponse({'response': response})

        elif stage == 'ask_action':
            if "book" in message:
                request.session['chat_stage'] = 'ask_name'
                return JsonResponse({'response': "Please enter your name to proceed with booking."})
            else:
                prompt = f"Answer this user query: {message}"
                r = requests.post(API_URL, json={"contents": [{"parts": [{"text": prompt}]}]})
                if r.status_code == 200:
                    try:
                        text = r.json()['candidates'][0]['content']['parts'][0]['text']
                        return JsonResponse({'response': text})
                    except Exception as e:
                        return JsonResponse({'response': f"Error parsing AI response: {str(e)}"})

        elif stage == 'ask_name':
            name = message.title()
            ticket = {
                'name': name,
                'source': request.session.get('source'),
                'destination': request.session.get('destination'),
                'mode': 'train',
                'distance': request.session.get('distance'),
                'cost': request.session.get('costs', {}).get('train'),
                'travel_date': request.session.get('travel_date'),
                'full_path': request.session.get('path', [])
            }
            request.session['ticket'] = ticket
            request.session['chat_stage'] = 'download'
            return JsonResponse({'response': f"Ticket booked for {name}. Say 'download ticket' to get your ticket."})

        elif stage == 'download':
            if "download" in message:
                ticket = request.session.get('ticket')
                if ticket:
                    path = request.session.get('path', [])
                    full_path = f"{ticket['source'].title()} → " + " → ".join(path) + f" → {ticket['destination'].title()}"
                    txt = (
                        f"----- Travel Ticket -----\n"
                        f"Passenger: {ticket['name']}\n"
                        f"Mode: {ticket['mode']}\n"
                        f"From: {ticket['source'].title()}\n"
                        f"To: {ticket['destination'].title()}\n"
                        f"Date: {ticket['travel_date']}\n"
                        f"Distance: {ticket['distance']} km\n"
                        f"Cost: ₹{ticket['cost']}\n"
                        f"Path: {full_path}\n"
                        f"-------------------------\n"
                    )
                    request.session['chat_stage'] = 'final_qa'
                    return JsonResponse({'response': txt + "\nThanks for booking. Happy journey!\nDo you have any other questions?"})

        elif stage == 'final_qa':
            if message in ["no", "no thanks", "exit"]:
                request.session['chat_stage'] = 'initial'
                return JsonResponse({'response': "Goodbye!"})
            else:
                prompt = f"Answer this user query: {message}"
                r = requests.post(API_URL, json={"contents": [{"parts": [{"text": prompt}]}]})
                if r.status_code == 200:
                    try:
                        text = r.json()['candidates'][0]['content']['parts'][0]['text']
                        return JsonResponse({'response': text + "\nDo you have any other questions?"})
                    except Exception as e:
                        return JsonResponse({'response': f"Error parsing AI response: {str(e)}"})

        return JsonResponse({'response': 'Sorry, I could not process your request.'})

    return JsonResponse({'response': 'Invalid method'})



# ---------------- Routes between cities ----------------
routes = {
    ('delhi', 'kolkata'): ['kanpur', 'varanasi', 'asansol'],
    ('delhi', 'mumbai'): ['jaipur', 'udaipur', 'nashik'],
    ('bangalore', 'hyderabad'): ['kurnool'],
    ('chennai', 'kolkata'): ['bhubaneswar'],
    ('delhi', 'pune'): ['jaipur', 'indore'],
    ('delhi', 'hyderabad'): ['agra', 'nagpur'],
    ('mumbai', 'kolkata'): ['nagpur', 'raipur', 'ranchi'],
    ('lucknow', 'mumbai'): ['jhansi', 'bhopal', 'nashik'],
    ('bangalore', 'mumbai'): ['hubli', 'pune'],
    ('delhi', 'chennai'): ['gwalior', 'nagpur', 'hyderabad'],
    ('kolkata', 'chennai'): ['bhubaneswar', 'visakhapatnam'],
    ('agra', 'pune'): ['indore', 'aurangabad'],
    ('guntur', 'hyderabad'): ['nalgonda'],
    ('palnadu', 'guntur'): ['sattenapalli'],

    # Andhra Pradesh routes
    ('vijayawada', 'guntur'): ['tenali'],
    ('guntur', 'nellore'): ['ongole'],
    ('tirupati', 'kadapa'): ['rayachoti'],
    ('guntur', 'visakhapatnam'): ['vijayawada', 'rajahmundry', 'kakinada'],
    ('vijayawada', 'tirupati'): ['nellore'],
    ('tirupati', 'chennai'): ['sriharikota'],
    ('visakhapatnam', 'srikakulam'): ['vizianagaram'],
    ('guntur', 'eluru'): ['vijayawada'],
    ('eluru', 'kakinada'): ['mandapeta'],
    ('nandyal', 'kurnool'): ['nalgonda'],
    ('markapur', 'kadapa'): ['proddatur'],
    ('machilipatnam', 'guntur'): ['repalle'],
    ('bapatla', 'guntur'): ['chirala'],
    ('vijayawada', 'raipur'): ['nagpur'],

    # Other regions
    ('coimbatore', 'bangalore'): ['mysore'],
    ('amritsar', 'delhi'): ['ludhiana', 'chandigarh'],
    ('jammu', 'delhi'): ['amritsar'],
    ('guwahati', 'kolkata'): ['shillong'],
    ('pune', 'hyderabad'): ['solapur'],
    ('mumbai', 'surat'): ['ahmedabad'],
    ('bhopal', 'nagpur'): ['betul'],
    ('ranchi', 'patna'): ['gaya'],
    ('jamshedpur', 'kolkata'): ['kharagpur']
}
routes.update({
    # Gujarat
    ('mumbai', 'ahmedabad'): ['surat'],
    ('ahmedabad', 'rajkot'): ['limdi'],
    ('ahmedabad', 'delhi'): ['udaipur', 'jaipur'],
    
    # Punjab / North
    ('delhi', 'amritsar'): ['panipat', 'ludhiana'],
    ('delhi', 'jammu'): ['panipat', 'ludhiana', 'amritsar', 'pathankot'],
    ('delhi', 'chandigarh'): ['panipat', 'ambala'],
    ('chandigarh', 'amritsar'): ['jalandhar', 'ludhiana'],

    # North East
    ('kolkata', 'guwahati'): ['bardhaman', 'malda', 'siliguri'],
    ('guwahati', 'shillong'): ['nagaon'],

    # South - Tamil Nadu and Kerala
    ('bangalore', 'coimbatore'): ['mysore'],
    ('coimbatore', 'madurai'): ['dindigul'],
    ('madurai', 'trivandrum'): ['tirunelveli', 'nagercoil'],
    ('kochi', 'trivandrum'): ['alleppey'],
    ('bangalore', 'trivandrum'): ['salem', 'madurai'],

    # Karnataka / Maharashtra
    ('bangalore', 'hubli'): ['davangere'],
    ('hubli', 'mumbai'): ['kolhapur', 'pune'],
    ('aurangabad', 'pune'): ['ahmednagar'],
    ('aurangabad', 'nagpur'): ['akola', 'amravati'],

    # Central / East India
    ('nagpur', 'raipur'): ['bhilai', 'durg'],
    ('raipur', 'jamshedpur'): ['ranchi'],
    ('jamshedpur', 'kolkata'): ['kharagpur'],

    # Andhra Pradesh + Correct Paths
    ('vijayawada', 'visakhapatnam'): ['eluru', 'rajahmundry'],
    ('visakhapatnam', 'srikakulam'): ['vizianagaram'],
    ('guntur', 'visakhapatnam'): ['vijayawada'],
    ('guntur', 'tirupati'): ['ongole', 'nellore'],
    ('guntur', 'anantapur'): ['kurnool'],
    ('tirupati', 'chennai'): ['sriharikota'],
    ('nellore', 'chennai'): ['sriharikota'],
    ('kurnool', 'hyderabad'): ['nalgonda'],
})



# ---------------- Auth Views ----------------
def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('trip_input')
    else:
        form = UserCreationForm()
    return render(request, 'smart_traverser/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect('trip_input')
    else:
        form = AuthenticationForm()
    return render(request, 'smart_traverser/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')

# ---------------- Trip Flow ----------------
@login_required
def trip_input_view(request):
    if request.method == 'POST':
        source = request.POST.get('source').lower()
        destination = request.POST.get('destination').lower()
        travel_date = request.POST.get('travel_date')

        if source not in city_coords or destination not in city_coords:
            return render(request, 'smart_traverser/trip_input.html', {'error': 'Invalid city name.'})

        request.session.update({
            'source': source,
            'destination': destination,
            'travel_date': travel_date
        })
        return redirect('budget_detail')
    return render(request, 'smart_traverser/trip_input.html')

@login_required
def budget_detail_view(request):
    src = request.session.get('source')
    dst = request.session.get('destination')
    travel_date = request.session.get('travel_date')

    if not src or not dst:
        return redirect('trip_input')

    def haversine(a, b):
        R = 6371
        lat1, lon1 = radians(a[0]), radians(a[1])
        lat2, lon2 = radians(b[0]), radians(b[1])
        dlat, dlon = lat2 - lat1, lon2 - lon1
        t = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
        return round(2 * atan2(sqrt(t), sqrt(1 - t)) * R, 2)

    distance = haversine(city_coords[src], city_coords[dst])
    costs = {
        'bus': round(distance * 5, 2),
        'train': round(distance * 3, 2),
        'flight': round(distance * 10, 2)
    }
    no_flight_list = ['guntur', 'palnadu', 'sattenapalli', 'kanpur']
    if src in no_flight_list or dst in no_flight_list:
        costs['flight'] = 0.0

    graph = build_graph(routes)
    path = find_path(graph, src, dst)
    if path:
        full_path = [city.title() for city in path]
    else:
        full_path = [src.title(), dst.title()]

    low_meal = {
        "Veg Meal": 50 + int(distance * 0.1),
        "Snacks": 30,
        "Tea/Coffee": 20,
        "Fruit Pack": 25
    }
    med_meal = {
        "Veg/Non-Veg Meal": 100 + int(distance * 0.15),
        "Juice": 50,
        "Sandwich": 60,
        "Biscuits": 20
    }
    high_meal = {
        "Premium Meal": 200 + int(distance * 0.2),
        "Drinks": 100,
        "Dessert": 80,
        "Luxury Snacks": 100
    }

    request.session['distance'] = distance
    request.session['costs'] = costs
    request.session['path'] = full_path
    request.session['low_meal'] = low_meal
    request.session['med_meal'] = med_meal
    request.session['high_meal'] = high_meal

    return render(request, 'smart_traverser/budget_detail.html', {
        'source': src.title(),
        'destination': dst.title(),
        'distance': distance,
        'travel_date': travel_date,
        'bus_cost': costs['bus'],
        'train_cost': costs['train'],
        'flight_cost': costs['flight'],
        'path': full_path,
        'low_meal': low_meal,
        'med_meal': med_meal,
        'high_meal': high_meal
    })

@login_required
def budget_options_view(request):
    source = request.session.get('source')
    destination = request.session.get('destination')
    distance = request.session.get('distance')
    costs = request.session.get('costs', {})
    path = request.session.get('path', [])

    return render(request, 'smart_traverser/budget_detail.html', {
        'source': source.title() if source else '',
        'destination': destination.title() if destination else '',
        'distance': distance,
        'bus_cost': costs.get('bus'),
        'train_cost': costs.get('train'),
        'flight_cost': costs.get('flight'),
        'path': path or [" "]
    })

@login_required
def book_ticket_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        source = request.POST.get('source')
        destination = request.POST.get('destination')
        mode = request.POST.get('mode')

        graph = build_graph(routes)
        path = find_path(graph, source, destination)
        if path:
            full_path = [city.title() for city in path]
        else:
            full_path = [source.title(), destination.title()]

        ticket = {
            'name': name,
            'source': source,
            'destination': destination,
            'mode': mode,
            'distance': request.session.get('distance'),
            'cost': request.session.get('costs', {}).get(mode.lower()),
            'travel_date': request.session.get('travel_date'),
            'full_path': full_path
        }

        request.session['ticket'] = ticket
        return render(request, 'smart_traverser/ticket.html', ticket)

    return redirect('trip_input')

@login_required
def download_ticket_view(request):
    ticket = request.session.get('ticket')
    if not ticket:
        return redirect('trip_input')

    path = request.session.get('path', 'Direct route')
    if isinstance(path, list):
        full_path = f"{ticket['source'].title()} → " + " → ".join(path) + f" → {ticket['destination'].title()}"
    else:
        full_path = path

    txt = (
        f"----- Travel Ticket -----\n"
        f"Passenger: {ticket['name']}\n"
        f"Mode: {ticket['mode']}\n"
        f"From: {ticket['source'].title()}\n"
        f"To: {ticket['destination'].title()}\n"
        f"Date: {ticket['travel_date']}\n"
        f"Distance: {ticket['distance']} km\n"
        f"Cost: ₹{ticket['cost']}\n"
        f"Path: {full_path}\n"
        f"-------------------------\n"
    )
    resp = HttpResponse(txt, content_type='text/plain')
    resp['Content-Disposition'] = 'attachment; filename="ticket.txt"'
    return resp
