#!/usr/bin/env python3
"""Load testing script for Global Credit Core API
Simulates 200 concurrent application creation requests across different countries
with valid document formats for each country.
"""

import asyncio
import random
import sys
from datetime import datetime

import aiohttp

# API Configuration
API_BASE_URL = "http://localhost:8000"
# Allow TOTAL_REQUESTS to be set via command line argument
TOTAL_REQUESTS = int(sys.argv[1]) if len(sys.argv) > 1 else 200
CONCURRENT_REQUESTS = 20  # Number of concurrent requests at a time

# Supported countries
COUNTRIES = ["ES", "PT", "IT", "MX", "CO", "BR"]

# Sample data for each country
SAMPLE_DATA = {
    "ES": {
        "names": ["Juan García López", "María Fernández Martínez", "Carlos Rodríguez Pérez"],
        "country_specific_data": {"province": "Madrid", "postal_code": "28001"}
    },
    "PT": {
        "names": ["João Silva Santos", "Maria Oliveira Costa", "António Pereira Sousa"],
        "country_specific_data": {"district": "Lisboa", "postal_code": "1000-001"}
    },
    "IT": {
        "names": ["Giovanni Rossi", "Maria Bianchi", "Giuseppe Romano"],
        "country_specific_data": {"region": "Lazio", "cap": "00100"}
    },
    "MX": {
        "names": ["Juan Pérez García", "María González López", "Carlos Hernández Martínez"],
        "country_specific_data": {"state": "CDMX", "postal_code": "01000"}
    },
    "CO": {
        "names": ["Juan Rodríguez Castro", "María López Torres", "Carlos Martínez Ruiz"],
        "country_specific_data": {"department": "Bogotá", "postal_code": "110111"}
    },
    "BR": {
        "names": ["João da Silva", "Maria dos Santos", "José de Oliveira"],
        "country_specific_data": {"state": "SP", "cep": "01000-000"}
    }
}


def generate_spain_dni() -> str:
    """Generate a valid Spanish DNI with correct checksum."""
    dni_letters = 'TRWAGMYFPDXBNJZSQVHLCKE'
    number = random.randint(10000000, 99999999)
    letter = dni_letters[number % 23]
    return f"{number}{letter}"


def generate_portugal_nif() -> str:
    """Generate a valid Portuguese NIF (9 digits)."""
    return str(random.randint(100000000, 999999999))


def generate_italy_cf() -> str:
    """Generate a mock Italian Codice Fiscale (16 characters alphanumeric)."""
    # Simplified version - real CF has complex checksum
    consonants = "BCDFGHLMNPRSTVZ"
    surname = ''.join(random.choice(consonants) for _ in range(3))
    name = ''.join(random.choice(consonants) for _ in range(3))
    year = str(random.randint(40, 99))
    month_codes = "ABCDEHLMPRST"
    month = random.choice(month_codes)
    day = str(random.randint(1, 31)).zfill(2)
    municipality = random.choice(["H501", "F205", "L219"])  # Rome, Milan, Turin codes
    checksum = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    return f"{surname}{name}{year}{month}{day}{municipality}{checksum}"


def generate_mexico_curp() -> str:
    """Generate a mock Mexican CURP (18 characters alphanumeric)."""
    # Simplified version - real CURP has complex validation
    consonants = "BCDFGHJKLMNPQRSTVWXYZ"
    vowels = "AEIOU"

    # First 4 chars: surname initial + surname vowel + paternal surname initial + name initial
    surname1 = random.choice(consonants) + random.choice(vowels)
    surname2 = random.choice(consonants)
    name = random.choice(consonants)

    # 6 digits: YYMMDD
    year = str(random.randint(40, 99))
    month = str(random.randint(1, 12)).zfill(2)
    day = str(random.randint(1, 28)).zfill(2)

    # Gender: H or M
    gender = random.choice(["H", "M"])

    # 2 letters: state code
    state = random.choice(["DF", "NL", "JC", "BC"])

    # 3 consonants from name parts
    consonants_part = ''.join(random.choice(consonants) for _ in range(3))

    # 2 final chars: homoclave
    homoclave = random.choice(consonants) + str(random.randint(0, 9))

    return f"{surname1}{surname2}{name}{year}{month}{day}{gender}{state}{consonants_part}{homoclave}"


def generate_colombia_cc() -> str:
    """Generate a Colombian Cédula de Ciudadanía (7-10 digits)."""
    return str(random.randint(10000000, 9999999999))


def generate_brazil_cpf() -> str:
    """Generate a valid Brazilian CPF with correct checksum."""
    # Generate first 9 random digits
    cpf_base = [random.randint(0, 9) for _ in range(9)]

    # Calculate first check digit
    sum1 = sum((10 - i) * cpf_base[i] for i in range(9))
    digit1 = (sum1 * 10 % 11) % 10
    cpf_base.append(digit1)

    # Calculate second check digit
    sum2 = sum((11 - i) * cpf_base[i] for i in range(10))
    digit2 = (sum2 * 10 % 11) % 10
    cpf_base.append(digit2)

    # Format: XXX.XXX.XXX-XX
    cpf_str = ''.join(map(str, cpf_base))
    return f"{cpf_str[:3]}.{cpf_str[3:6]}.{cpf_str[6:9]}-{cpf_str[9:]}"


def generate_document(country: str) -> str:
    """Generate a valid identity document for the given country."""
    generators = {
        "ES": generate_spain_dni,
        "PT": generate_portugal_nif,
        "IT": generate_italy_cf,
        "MX": generate_mexico_curp,
        "CO": generate_colombia_cc,
        "BR": generate_brazil_cpf
    }
    return generators[country]()


def generate_application_data(country: str) -> dict:
    """Generate realistic application data for a given country."""
    data = SAMPLE_DATA[country]

    # Generate valid document
    document = generate_document(country)

    # Random values
    random_amount = random.randint(1000, 50000)
    random_age = random.randint(18, 75)
    random_monthly_income = random.randint(2000, 15000)

    return {
        "full_name": random.choice(data["names"]),
        "identity_document": document,
        "country": country,
        "requested_amount": random_amount,
        "currency": "EUR" if country in ["ES", "PT", "IT"] else "USD",
        "age": random_age,
        "monthly_income": random_monthly_income,
        "country_specific_data": data["country_specific_data"]
    }


async def create_application(session: aiohttp.ClientSession, app_data: dict, request_num: int) -> dict:
    """Create a single application."""
    try:
        async with session.post(
            f"{API_BASE_URL}/api/v1/applications",
            json=app_data,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as response:
            result = await response.json()
            status = response.status

            return {
                "request_num": request_num,
                "country": app_data["country"],
                "status": status,
                "success": status == 201,
                "response": result if status == 201 else result.get("detail", "Unknown error")
            }
    except Exception as e:
        return {
            "request_num": request_num,
            "country": app_data["country"],
            "status": 0,
            "success": False,
            "response": str(e)
        }


async def run_load_test():
    """Run the load test with concurrent requests."""
    print(f"🚀 Starting load test: {TOTAL_REQUESTS} requests across {len(COUNTRIES)} countries")
    print(f"📊 Concurrent requests: {CONCURRENT_REQUESTS}")
    print("-" * 80)

    # Generate all application data
    applications = []
    for i in range(TOTAL_REQUESTS):
        country = random.choice(COUNTRIES)
        app_data = generate_application_data(country)
        applications.append((i + 1, app_data))

    # Statistics counters
    results_by_country = {country: {"success": 0, "failed": 0} for country in COUNTRIES}
    total_success = 0
    total_failed = 0

    start_time = datetime.now()

    # Create HTTP session
    async with aiohttp.ClientSession() as session:
        # Process requests in batches
        for i in range(0, len(applications), CONCURRENT_REQUESTS):
            batch = applications[i:i + CONCURRENT_REQUESTS]
            tasks = [
                create_application(session, app_data, request_num)
                for request_num, app_data in batch
            ]

            # Wait for batch to complete
            results = await asyncio.gather(*tasks)

            # Update statistics
            for result in results:
                country = result["country"]
                if result["success"]:
                    results_by_country[country]["success"] += 1
                    total_success += 1
                    print(f"✅ Request {result['request_num']:3d} [{country}]: SUCCESS")
                else:
                    results_by_country[country]["failed"] += 1
                    total_failed += 1
                    # Only print first 20 errors to avoid clutter
                    if total_failed <= 20:
                        print(f"❌ Request {result['request_num']:3d} [{country}]: FAILED - {result['response']}")

            # Small delay between batches to avoid overwhelming the server
            await asyncio.sleep(0.1)

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    # Print summary
    print("\n" + "=" * 80)
    print("📈 LOAD TEST SUMMARY")
    print("=" * 80)
    print(f"Total Requests: {TOTAL_REQUESTS}")
    print(f"Successful: {total_success} ({total_success / TOTAL_REQUESTS * 100:.1f}%)")
    print(f"Failed: {total_failed} ({total_failed / TOTAL_REQUESTS * 100:.1f}%)")
    print(f"Duration: {duration:.2f} seconds")
    print(f"Requests/sec: {TOTAL_REQUESTS / duration:.2f}")
    print("\n📊 Results by Country:")
    print("-" * 80)
    for country in COUNTRIES:
        stats = results_by_country[country]
        total = stats["success"] + stats["failed"]
        success_rate = (stats["success"] / total * 100) if total > 0 else 0
        print(f"  {country}: {stats['success']}/{total} successful ({success_rate:.1f}%)")
    print("=" * 80)
    print("\n✨ Load test complete! Check Grafana dashboard for metrics:")
    print("   http://localhost:3000/d/global-credit-overview")


if __name__ == "__main__":
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║  Global Credit Core - Load Testing Script                 ║
    ║  Simulating 200 concurrent application requests           ║
    ║  With valid document formats for each country             ║
    ╚════════════════════════════════════════════════════════════╝
    """)

    asyncio.run(run_load_test())
