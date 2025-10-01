import requests
from django.core.management.base import BaseCommand
from dashboard.models import Speciality, SubSpeciality, Residency, Nationality, CountryCode

API_HEADERS = {
    "Accept-Language": "en",
    "Accept": "application/json",
    "Country-Id": "84",
    "Currency-Id": "66",
    "Content-Type": "application/json",
    "platform": "ios",
}


class Command(BaseCommand):
    help = "Fetch Master Data: Specialities, SubSpecialities, Residency, Nationality, Country Codes"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("=== Fetching Master Data ==="))

        # Fetch all data
        self.fetch_specialities()
        self.fetch_residencies()
        self.fetch_countries()

        self.stdout.write(self.style.SUCCESS("=== Master Data Sync Completed ✅ ==="))

    # ---------------- Specialities & Sub-specialities ----------------
    def fetch_specialities(self):
        self.stdout.write(self.style.SUCCESS("Fetching Specialities..."))
        page = 0
        count = 50
        while True:
            url = f"https://medicalsupplierz.app/api/common/get_specialties/3457?pagination=0&count={count}&page={page}"
            try:
                res = requests.get(url, headers=API_HEADERS, timeout=15)
                res.raise_for_status()
                data = res.json().get("data", [])
                if not data:
                    break

                for item in data:
                    name = item.get("name")
                    if not name:
                        continue

                    speciality, created = Speciality.objects.get_or_create(name=name)
                    if created:
                        self.stdout.write(self.style.SUCCESS(f"Added Speciality: {speciality.name}"))
                    else:
                        self.stdout.write(self.style.WARNING(f"Speciality exists: {speciality.name}"))

                    # Sub-specialities
                    speciality_id = item.get("id")
                    if speciality_id:
                        sub_page = 0
                        while True:
                            sub_url = f"https://medicalsupplierz.app/api/common/get_sub_specialties?specialty_id={speciality_id}&pagination=0&count={count}&page={sub_page}"
                            sub_res = requests.get(sub_url, headers=API_HEADERS, timeout=15)
                            sub_res.raise_for_status()
                            sub_data = sub_res.json().get("data", [])
                            if not sub_data:
                                break
                            for sub in sub_data:
                                sub_name = sub.get("name")
                                if sub_name:
                                    sub_obj, sub_created = SubSpeciality.objects.get_or_create(
                                        speciality=speciality,
                                        name=sub_name
                                    )
                                    if sub_created:
                                        self.stdout.write(self.style.SUCCESS(f"  Added SubSpeciality: {sub_name}"))
                                    else:
                                        self.stdout.write(self.style.WARNING(f"  SubSpeciality exists: {sub_name}"))
                            sub_page += 1

                page += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Speciality fetch failed: {e}"))
                break
        self.stdout.write(self.style.SUCCESS("Specialities & SubSpecialities ✅"))

    # ---------------- Residencies ----------------
    def fetch_residencies(self):
        self.stdout.write(self.style.SUCCESS("Fetching Residencies..."))
        page = 0
        count = 50
        while True:
            url = f"https://medicalsupplierz.app/api/common/get_residencies?null=null&pagination=0&count={count}&page={page}"
            try:
                res = requests.get(url, timeout=15)
                res.raise_for_status()
                data = res.json().get("data", [])
                if not data:
                    break
                for item in data:
                    country_name = item.get("name")
                    if country_name:
                        obj, created = Residency.objects.get_or_create(country=country_name)
                        if created:
                            self.stdout.write(self.style.SUCCESS(f"Added Residency: {country_name}"))
                        else:
                            self.stdout.write(self.style.WARNING(f"Residency exists: {country_name}"))
                page += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Residency fetch failed: {e}"))
                break
        self.stdout.write(self.style.SUCCESS("Residencies ✅"))

    # ---------------- Nationalities & Country Codes ----------------
    def fetch_countries(self):
        self.stdout.write(self.style.SUCCESS("Fetching Nationality & Country Codes..."))
        try:
            url = "https://restcountries.com/v3.1/all?fields=name,idd,cca2"
            res = requests.get(url, timeout=15)
            res.raise_for_status()
            data = res.json()

            for country in data:
                name = country.get("name", {}).get("common")
                if not name:
                    continue

                # Nationality
                nationality, created = Nationality.objects.get_or_create(country=name)
                if created:
                    self.stdout.write(self.style.SUCCESS(f"Added Nationality: {name}"))
                else:
                    self.stdout.write(self.style.WARNING(f"Nationality exists: {name}"))

                # Country Codes
                idd = country.get("idd", {})
                root = idd.get("root", "")
                suffixes = idd.get("suffixes", [""]) or [""]

                for suffix in suffixes:
                    code = f"{root}{suffix}" if root else None
                    if code:
                        cc, cc_created = CountryCode.objects.get_or_create(code=code)
                        cc.countries.add(nationality)
                        if cc_created:
                            self.stdout.write(self.style.SUCCESS(f"Added CountryCode: {code} → {name}"))
                        else:
                            self.stdout.write(self.style.WARNING(f"CountryCode exists: {code} → {name}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Country fetch failed: {e}"))
        self.stdout.write(self.style.SUCCESS("Nationality & CountryCode ✅"))
