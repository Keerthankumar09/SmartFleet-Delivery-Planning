
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.planning.constraints import (
    check_vehicle_capacity,
    check_shift,
    check_time_window,
    check_route_duration,
    check_delivery_service,
)


def main():
    passed = 0
    failed = 0

    def test(name, condition):
        nonlocal passed, failed

        if condition:
            print(f"PASS: {name}")
            passed += 1
        else:
            print(f"FAIL: {name}")
            failed += 1

    # 1. Vehicle capacity
    result = check_vehicle_capacity(50, 500, 100, 1000)
    test("Vehicle capacity valid", result["valid"])

    result = check_vehicle_capacity(120, 500, 100, 1000)
    test("Vehicle unit capacity exceeded", not result["valid"])

    # 2. Driver shift
    result = check_shift(
        "2026-10-22T09:00:00",
        "2026-10-22T16:00:00",
        "2026-10-22T08:00:00",
        "2026-10-22T17:00:00",
    )
    test("Route within driver shift", result["valid"])

    result = check_shift(
        "2026-10-22T07:00:00",
        "2026-10-22T16:00:00",
        "2026-10-22T08:00:00",
        "2026-10-22T17:00:00",
    )
    test("Route starting before shift rejected", not result["valid"])

    # 3. Time windows
    hard_window = {
        "window_start": "2026-10-22T10:00:00",
        "window_end": "2026-10-22T12:00:00",
        "window_type": "HARD",
    }

    result = check_time_window(
        "2026-10-22T11:00:00", hard_window
    )
    test("Arrival inside hard window", result["valid"])

    result = check_time_window(
        "2026-10-22T13:00:00", hard_window
    )
    test("Late arrival outside hard window rejected", not result["valid"])

    soft_window = {
        **hard_window,
        "window_type": "SOFT",
    }

    result = check_time_window(
        "2026-10-22T13:00:00", soft_window
    )
    test(
        "Late arrival in soft window allowed with penalty",
        result["valid"] and result["penalty_minutes"] == 60,
    )

    # 4. Route duration
    result = check_route_duration(
        "2026-10-22T08:00:00",
        "2026-10-22T16:00:00",
        600,
    )
    test("Route duration within limit", result["valid"])

    result = check_route_duration(
        "2026-10-22T08:00:00",
        "2026-10-22T19:00:00",
        600,
    )
    test("Route duration limit enforced", not result["valid"])

    # 5. Service duration
    result = check_delivery_service(
        "2026-10-22T10:00:00",
        "2026-10-22T10:30:00",
        30,
    )
    test("Required service duration respected", result["valid"])

    result = check_delivery_service(
        "2026-10-22T10:00:00",
        "2026-10-22T10:15:00",
        30,
    )
    test("Insufficient service duration rejected", not result["valid"])

    print("\n----------------------------")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print("----------------------------")

    if failed:
        raise SystemExit(1)

    print("ALL CONSTRAINT TESTS PASSED")


if __name__ == "__main__":
    main()
