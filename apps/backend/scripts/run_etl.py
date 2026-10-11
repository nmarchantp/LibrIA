"""Carga únicamente días cerrados; repetir una fecha exitosa no vuelve a escribir."""
import argparse
import json
from datetime import date, timedelta
from app.modules.analytics.etl import last_closed_day, run_day, run_pending


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date', type=date.fromisoformat, help='Día cerrado YYYY-MM-DD')
    parser.add_argument('--from-date', type=date.fromisoformat, help='Inicialización histórica hasta el último día cerrado')
    args = parser.parse_args()
    if args.date and args.from_date:
        parser.error('Usa --date o --from-date, no ambos')
    if args.from_date:
        if args.from_date > last_closed_day():
            parser.error('La fecha inicial debe estar cerrada')
        day = args.from_date
        while day <= last_closed_day():
            result = run_day(day)
            print(json.dumps(result))
            if result['status'] == 'busy':
                raise SystemExit(1)
            day += timedelta(days=1)
    elif args.date:
        print(json.dumps(run_day(args.date)))
    else:
        print(json.dumps(run_pending()))


if __name__ == '__main__':
    main()
