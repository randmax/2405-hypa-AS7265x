if __name__ == "__main__":
    from bootstrap import bootstrap_or_exit
    bootstrap_or_exit()

import argparse
import time
import serial


def main():
    parser = argparse.ArgumentParser(description="Minimal serial monitor (Windows / Linux)")
    parser.add_argument("port", help="COM3 or /dev/ttyUSB0")
    parser.add_argument("baud", type=int, nargs="?", default=115200)
    args = parser.parse_args()
    try:
        with serial.serial_for_url(args.port, args.baud, timeout=0.2) as connection:
            print("Opened", args.port, "at", args.baud, "baud. Ctrl+C to stop.")
            time.sleep(2)
            while True:
                line = connection.readline().decode("utf-8", errors="replace").strip()
                if line:
                    print(line)
    except KeyboardInterrupt:
        print("Stopped; serial port closed.")
    except (serial.SerialException, ValueError, OSError) as exc:
        parser.exit(1, "Could not use port: {}\n".format(exc))


if __name__ == "__main__":
    main()
