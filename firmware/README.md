# AS7265xController – Arduino Nano

Ez az Arduino program közvetlenül, a dokumentált virtuális I²C-regisztereken vezérli az AS72651/52/53 chipsetet. Nem igényli a SparkFun könyvtár telepítését. A referencia a projektben megadott `AS7265x_DS000612_1-00.pdf`; a fájl belső oldalcímei **DS000612 v1-04, 2018-07-09** verziót jeleznek. A fontos részek: 23–27. oldal (virtuális I²C), 28–37. oldal (regiszterek), 31–33. oldal (mérési és LED-beállítások). [Gyártói adatlap](https://look.ams-osram.com/m/76ce4c0d80cd1565/original/AS7265x-DS000612.pdf).

## Bekötés

| Arduino Nano | Szenzorpanel |
|---|---|
| A4 / SDA | SDA |
| A5 / SCL | SCL |
| GND | GND |
| Panelnek megfelelő táp | VIN / 3V3 a panel kialakítása szerint |

A klasszikus Nano 5 V-os logikával dolgozik, az AS7265x adatlap szerinti logikája 3,3 V-os. Ha a panel nem tartalmaz megfelelő illesztést, az A4/A5 és a szenzor közé kétirányú I²C-szintillesztő szükséges. A szenzoroldalon 3,3 V-os felhúzókat használj. A firmware 400 kHz I²C-t használ; a panel jumperét I²C üzemmódba kell állítani. A felhasználó által megadott **SCL=A5, SDA=A4** bekötés ezt követi.

Az alapértelmezett LED-kiosztás a SparkFun Spectral Triadnak felel meg: AS72651 → fehér, AS72652 → IR, AS72653 → UV. Más panelen az adott chip LED_DRV kimenetéhez ténylegesen bekötött LED működik; a színnevet nem a chip határozza meg. A három LED_IND kimenet külön vezérelhető, ha a panelen ki vannak építve.

## Fordítás és UART-os frissítés

Arduino CLI és az **Arduino AVR Boards 1.8.6** core szükséges:

```sh
arduino-cli core update-index
arduino-cli core install arduino:avr@1.8.6
```

A Python-indító ugyanazt a projekt-venv-et használja, mint az alkalmazás:

```sh
python firmware/manage.py build --board nano
python firmware/manage.py build --board nano-old
```

Windows alatt `python` helyett `py -3`, Linux alatt `python3` is használható. Ha a CLI nincs a PATH-on: `--cli "teljes/utvonal/arduino-cli"`. A fordítás nem nyit meg soros portot és nem programozza át a panelt.

UART-feltöltéshez zárd le a kapcsolatot a GUI-ban és a Serial Monitorban, majd:

```sh
# Windows példa; a saját portodat add meg:
py -3 firmware/manage.py upload --board nano --port COM3
# Linux példa:
python3 firmware/manage.py upload --board nano --port /dev/ttyUSB0
```

Régebbi Nano bootloaderhez válaszd a `nano-old` profilt. A `nano` profil 115200, a `nano-old` 57600 baudon programoz; a mérőprogram kommunikációja mindkettőn **115200 baud, 8N1**. A Nano beépített USB–UART kapcsolata és automatikus resetje használható. Külső USB–TTL adapter esetén TX↔RX, RX↔TX, GND és az automatikus resethez megfelelő DTR/RESET kapcsolat kell; a TTL/UART nem ±RS-232 feszültségszint.

### A bootloader helye

A bootloader külön flash-területen fut; nem lehet egy futó Arduino sketch részeként, UART-on egy teljesen üres Nano chipre felírni. A core fordítása kétféle képet készít:

- `AS7265xController.ino.hex`: az alkalmazás, **ezt tölti fel UART-on** az indító.
- `AS7265xController.ino.with_bootloader.hex`: az alkalmazás és a kiválasztott standard bootloader egyesített képe, első programozáshoz / helyreállításhoz **ISP-n**.

Az előre lefordított Nano és Nano Old Bootloader képek a `releases/` könyvtárban találhatók, SHA-256 ellenőrző manifesttel. Az egyesített HEX nem állítja be magától a fuse biteket. Hiányzó vagy sérült bootloader esetén először az Arduino IDE **Burn Bootloader**, vagy egy valódi ISP-programozóval a CLI használható; a core a megfelelő fuse és lock beállításokat kezeli:

```sh
# Példa Arduino as ISP programozóval; csak tudatos első programozáskor futtasd:
python firmware/manage.py burn-bootloader --board nano --port COM4 --programmer arduinoasisp
```

Utána a normál `upload` már UART-on működik. [Arduino hivatalos bootloader-útmutató](https://support.arduino.cc/hc/en-us/articles/4841602539164-Burn-the-bootloader-on-UNO-Mega-and-classic-Nano-using-another-Arduino).

Ez a funkció az **Arduino programját** frissíti. Az AS7265x gyári, külső soros flashben tárolt firmware-ét nem cseréli le, és nem igényel hozzá gyártói bináris állományt.

## Mérés és panelvezérlés

- Induláskor minden megvilágító és jelző LED kikapcsolt, a driveráram 12,5 mA, a jelzőáram 1 mA. A szenzor erősítése 16×, az integráció 10 ciklus/bank, a kimenet kalibrált.
- A 18 csatorna két integrációs bankot használ: a névleges konverziós idő körülbelül `2 × ciklus × 2,8 ms`; ehhez hozzáadódik a kiolvasás és a soros átvitel. A regiszter értéke `ciklus−1` (0..255), a GUI 1..256 ciklust mutat. Rövidebb integráció gyorsabb, de zajosabb és kisebb maximális ADC-tartományú mérést eredményez.
- A program nem blokkoló one-shot állapotgépet használ: konverzió közben fogadja a parancsokat, majd a teljes konverzióból kiolvassa mind a 18 csatornát. Minden regiszterkézfogásnak időkorlátja van, a polling 100 µs-os, nem fix 5 ms-os várakozásokkal működik.
- A PC-programban a **Nano / szenzor vezérlése** szekció az új firmware felismerése után aktiválódik. A demó ugyanezt a protokollt szimulálja.
- A LED-ek ki-/bekapcsolhatók; áramuk 12,5 / 25 / 50 / 100 mA. A jelző LED-ek árama 1 / 2 / 4 / 8 mA. A beállítás akkor tekinthető alkalmazottnak, amikor a Nano visszaigazolta.
- Állítható az erősítés (1× / 3,7× / 16× / 64×), az integráció és a nyers/kalibrált formátum. Ezek változásakor a PC üríti a mérési előzményt, hogy különböző formátumokat vagy expozíciókat ne átlagoljon össze.
- Az adatküldés szüneteltethető a port lezárása nélkül; szünetben külön egy mérés is kérhető. Egy már elindított konverzió még befejeződhet a szüneteltetés után.
- A három chip hőmérséklete külön lekérdezhető; rendszeresen automatikus telemetria is érkezik.
- A PC kapcsolatlezáráskor kikapcsoló parancsot küld. A firmware a host életjelének 6 másodperces kimaradása után is megpróbálja kikapcsolni a LED-eket. I²C-/hardverhiba esetén a fizikai kapcsolás sikere nem garantálható; a válasz hibát jelez.

## Soros protokoll, 1. verzió

A mérések a korábbi 18 oszlopos CSV-formátumot használják, sorrendjük: `A B C D E F G H R I S J T U V W K L` (410..940 nm). A vezérlési válaszok `#` előtagú JSON-sorok. A kérésazonosító 1..65535, a 0 aszinkron értesítéshez / életjelhez fenntartott.

| Kérés | Hatás |
|---|---|
| `@1 INFO` | Protokollverzió, firmware, MCU és képességek, utána állapot |
| `@2 STATE` | Tényleges beállítások |
| `@3 LED 0 1 0` | Fehér driver be, 12,5 mA (`device enabled current_code`) |
| `@4 IND 2 0 1` | AS72653 jelző ki, 2 mA |
| `@5 SET 2 10 calibrated` | 16× gain, 10 ciklus/bank, kalibrált adatok |
| `@6 SET 1 20 raw` | 3,7× gain, 20 ciklus/bank, nyers ADC |
| `@7 TEMP` | Három hőmérséklet |
| `@8 RUN 0` / `@9 RUN 1` | Folyamatos adatküldés szünet / folytatás |
| `@10 SHOT` | Egy teljes mérés, ha a folyamatos mérés szünetel |
| `@11 OFF` | Minden LED kikapcsolása |
| `@0 PING` | Host életjel; válasz `pong` |

Az áramkódok 0..3 a fenti növekvő áramértékeket jelentik. Minden parancsot LF zár le. A Nano legfeljebb 95 karakteres parancsot fogad; túl hosszú sor után a következő LF-nél helyreáll. Hibás/hiányos/tartományon kívüli parancs `error` választ ad. A PC 3 másodperc után jelzi a hiányzó visszaigazolást. Régi CSV-only firmware esetén a mérés változatlanul olvasható, a panelvezérlők letiltva maradnak.
