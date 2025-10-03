import requests
from django.core.management.base import BaseCommand
from dashboard.models import Country, State, City, Nationality, CountryCode

# Headers for APIs (if required)
API_HEADERS = {
    "Accept": "application/json",
}


class Command(BaseCommand):
    help = "Fetch Countries, States, Cities, Nationalities and Country Codes"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("=== Fetching Location Data ==="))

        self.fetch_countries_and_codes()
        self.fetch_states_and_cities()

        self.stdout.write(self.style.SUCCESS("=== Location Data Sync Completed ✅ ==="))

    # ---------------- Countries & Country Codes ----------------
    def fetch_countries_and_codes(self):
        self.stdout.write(self.style.SUCCESS("Fetching Countries and Country Codes..."))
        try:
            url = "https://restcountries.com/v3.1/all?fields=name,idd"
            res = requests.get(url, timeout=15)
            res.raise_for_status()
            data = res.json()

            for country in data:
                name = country.get("name", {}).get("common")
                if not name:
                    continue

                # Country table
                country_obj, _ = Country.objects.get_or_create(name=name)

                # Nationality table
                nationality, _ = Nationality.objects.get_or_create(country=name)

                # Country codes
                idd = country.get("idd", {})
                root = idd.get("root", "")
                suffixes = idd.get("suffixes", [""]) or [""]

                for suffix in suffixes:
                    code = f"{root}{suffix}" if root else None
                    if code:
                        cc, _ = CountryCode.objects.get_or_create(code=code)
                        cc.countries.add(nationality)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Country & CountryCode fetch failed: {e}"))
        self.stdout.write(self.style.SUCCESS("Countries & Country Codes ✅"))

    # ---------------- States & Cities ----------------
    def fetch_states_and_cities(self):
        self.stdout.write(self.style.SUCCESS("Fetching States and Cities..."))
        try:
            url = "https://countriesnow.space/api/v0.1/countries/states"
            res = requests.get(url, timeout=15)
            res.raise_for_status()
            countries_data = res.json().get("data", [])

            for country_item in countries_data:
                country_name = country_item.get("name")
                if not country_name:
                    continue

                country_obj, _ = Country.objects.get_or_create(name=country_name)

                states = country_item.get("states", [])
                for state_item in states:
                    state_name = state_item.get("name")
                    if not state_name:
                        continue

                    state_obj, _ = State.objects.get_or_create(name=state_name, country=country_obj)

                    # Fetch cities for this state
                    cities_url = "https://countriesnow.space/api/v0.1/countries/state/cities"
                    payload = {"country": country_name, "state": state_name}
                    city_res = requests.post(cities_url, json=payload, timeout=15)
                    if city_res.status_code != 200:
                        continue
                    cities_data = city_res.json().get("data", [])
                    for city_name in cities_data:
                        if city_name:          
                            City.objects.get_or_create(name=city_name, state=state_obj)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"States & Cities fetch failed: {e}"))
        self.stdout.write(self.style.SUCCESS("States & Cities ✅"))
