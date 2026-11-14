"""Run ten real HTTP readiness checks. Start the API before running this script."""
import argparse
import json
from time import perf_counter
from urllib.request import urlopen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/v1/health")
    arguments = parser.parse_args()
    latencies = []
    for index in range(10):
        started = perf_counter()
        with urlopen(arguments.url, timeout=10) as response:
            payload = json.load(response)
            if response.status != 200 or payload.get("db") != "connected" or not payload.get("pgvector"):
                raise SystemExit("Readiness check failed")
        latency = round((perf_counter() - started) * 1000, 2)
        latencies.append(latency)
        print(json.dumps({"check": index + 1, "status": "passed", "latency_ms": latency}))
    print(json.dumps({"passed": 10, "total": 10, "max_latency_ms": max(latencies)}))


if __name__ == "__main__":
    main()
