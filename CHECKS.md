# Ellenőrzési jegyzőkönyv – 2026-11-06

## Automatizált ellenőrzések

| Környezet | Eredmény |
|---|---|
| Windows, Python 3.12.10, Matplotlib 3.10.1, NumPy 2.2.5 | 35 teszt: 33 sikeres, Linux PTY és g++ harness kihagyva |
| Windows, Python 3.9.13, Matplotlib 3.9.4, NumPy 2.0.2 | 35 teszt: 33 sikeres, Linux PTY és g++ harness kihagyva |
| Ubuntu 22.04 / WSL, Python 3.10.12, Matplotlib 3.10.9, NumPy 2.2.6, Tk / Xvfb | Mind a 35 teszt sikeres, valódi pyserial PTY és natív firmware harness mellett |

Ellenőrzött viselkedés: 18 csatornás parser, záró vessző, NaN/Inf és hibás sorok elutasítása, darabolt sorok összefűzése, túl hosszú sor utáni helyreállás, gördülő átlag, pufferkorlát és sorrend, eredeti adatok CSV-exportja, megszakítás telt eseménysor mellett, portlezárás, ismételt indítás/leállítás, leállítás utáni menthetőség, újrahasznált diagramobjektumok, waterfall időiránya, témaváltás állapotmegőrzéssel, nézetenként megőrzött tengelyhatárok, kattintáshoz kötött görgőkezelés, korlátozott napló, hosszú státuszszöveg, 150%-os skálázásnál a bitmap és a vászon méretének egyezése, témázott buboréksúgó és erőforrás-felszabadítása.

A Python 3.9-hez feloldott Matplotlib/Pillow páros külső `DeprecationWarning` üzenetet adhat a toolbar ikonjainak létrehozásakor; az ellenőrzések ettől sikeresek. A függőségkorlátok mellett a pip a használt Pythonhoz kompatibilis csomagverziókat választja.

## Élő megjelenítés késleltetésének javítása

A korábbi hisztogram a teljes, alapból 50 elemű előzménypuffer átlagát mutatta. Ez nem azonos az élő méréssel: például 2 Hz-es forrásnál a régi értékek teljes kicserélődése 25 másodpercig tart. Most a hisztogram alapértéke 1 mintás, és a legfrissebb teljes spektrum mind a 18 csatornáját jeleníti meg. Az opcionális átlagolás külön vezérlőt kapott; a CSV és a waterfall előzménypuffere megmaradt.

A munkaszál az érvényes mintákat közvetlenül szálbiztos pufferbe írja. A GUI a friss puffer pillanatképét olvassa, így egy lassú rajzolás, szöveges soráradat vagy megállított GUI nem okoz régi mérési eseményekből álló sorban állást. Az értesítési sor telítődésekor a diagnosztika összevonódik, az adatfogadás halad tovább. A képernyőfrissítés felső korlátja 20 Hz; az ütemezés a tényleges rajzolás befejezését is figyelembe veszi.

Az új regressziós tesztek ellenőrzik:

- 1000 mintás előzmény után is azonnal a legutolsó sor jelenik meg mind a 18 oszlopon; az átlagolás külön bekapcsolható.
- 5000 teljes spektrum és 2000 diagnosztikai sor fogyasztó nélkül, telt GUI-eseménysor mellett is feldolgozható. A fogadott minták száma pontos, a legutolsó 64 eredeti minta sorrendje és értéke megmarad.
- GUI-szünet után az első kirajzolt képkocka a legfrissebb fogadott mintát tartalmazza, nem a sorban álló régi adatokat.

Szintetikus terhelésmérés Ubuntu/WSL és Xvfb alatt, 150%-os Tk-skálázással, 1000 mintás pufferrel, 200 spektrum/s célsebességgel, nézetenként 4 másodpercig:

| Nézet | Elküldött / fogadott minták | Medián | 95. percentilis | Maximum | Első képkocka 500 ms GUI-szünet után |
|---|---|---|---|---|---|
| Histogram | 771 / 771 | 108 ms | 141 ms | 153 ms | 123 ms |
| Waterfall | 766 / 766 | 141 ms | 167 ms | 169 ms | 135 ms |

Az idő a szintetikus sor elküldésétől a Matplotlib `draw_event` eseményéig értendő. Ez szoftveres terhelésmérés, nem az érzékelő mérésétől a monitor fizikai frissüléséig tartó hardveres késleltetés mérése. A fogadás a GUI-szünet alatt is folytatódott; nem keletkezett visszajátszandó mérési eseménysor.

## Nano firmware, bootloader és panelvezérlés

- A megadott adatlap teljes regiszter- és I²C-fejezete alapján készült önálló virtuálisregiszter-driver. Az integráció és a LED-regiszter táblázata vizuálisan is ellenőrizve; a kapott fájl belső verziója DS000612 v1-04.
- Arduino CLI 1.5.1 és Arduino AVR Boards 1.8.6 mellett sikeres a Nano (`atmega328`) és Nano Old Bootloader (`atmega328old`) fordítása: **11752 bájt flash**, **614 bájt statikus RAM**, mindkét profilon. Sem UART-os feltöltés, sem ISP-programozás nem történt fizikai eszközre.
- Mindkét profilhoz létrejött az alkalmazás HEX és az alkalmazás+bootloader HEX. A tesztek ellenőrzik a SHA-256 manifestet, a forrásegyezést, minden Intel HEX sor ellenőrzőösszegét és a bootloader flash-címtartományának jelenlétét.
- A tényleges `.ino` és I²C-driver natív g++ környezetben, virtuális Wire/Serial eszközzel fut. Ellenőrzött: hat LED vezérlőbitjei és áramkódjai, integrációs regiszter ciklus−1 leképezése, erősítés/nyers mód, 18 csatorna sorrendje, big-endian float/uint16 kiolvasás, hibás parancsok és I²C-hiba elutasítása, negatív hőmérséklet, egyszeri mérés, életjel utáni automatikus LED-kikapcsolás, túl hosszú sor utáni helyreállás. Az így kiírt JSON/CSV sorokat a PC saját parsere is ellenőrzi.
- A GUI-tesztek lefedik a demó parancsvisszaigazolásait, a prioritásos „minden LED ki” műveletet, a törölt parancs utáni UI-feloldást, hiba esetén az utolsó igazolt állapot visszaállítását, a szünet/egyszeri mérést, a nyers módra váltáskor ürített puffert és a régi CSV-firmware letiltott vezérlőit.
- A Nano kezelőszekció világos és fekete témában, 150%-os Tk-skálázással képen is ellenőrizve, a görgetés felső és alsó részén is.

## Folyamatosabb hisztogram – részleges újrarajzolás

A hisztogram animált oszlopait külön rajzoljuk a gyorsítótárazott háttérre; a tengelyek, szövegek és rács csak szükség esetén épülnek újra. Az automatikus skála kerekített határokra vált, és kis ingadozásnál nem kényszerít teljes újrarajzolást. A témaváltás, zoom, resize és nyers/kalibrált mértékegységváltás frissíti a hátteret. Külön teszt bizonyítja, hogy az oszlopfrissítés nem vált ki teljes `draw_event` eseményt, és a mentett PNG-ben is megmaradnak az animált oszlopok.

Az előző terhelésméréshez hasonló Ubuntu/Xvfb, 150%-os Tk, 1000 mintás puffer és 200 Hz célsebesség mellett, nézetenként 4 másodperc alatt (ebből 500 ms szándékos GUI-szünet):

| Nézet | Elküldött / fogadott minták | Kirajzolt képkockák | Medián | 95. percentilis | Maximum | Első képkocka GUI-szünet után |
|---|---|---|---|---|---|---|
| Histogram, blitting | 757 / 757 | 75 | 6,5 ms | 9,0 ms | 152,4 ms | 7,3 ms |
| Waterfall | 771 / 771 | 20 | 138,3 ms | 197,0 ms | 197,8 ms | 150,6 ms |

A mérés most a közös képkocka-visszajelzést használja: gyors rajzolásnál a Tk-blit visszatérését, teljes rajzolásnál a Matplotlib rajzolási eseményét. A 152 ms-os maximum az első teljes rajzolást is tartalmazza. A korábbi teljes rajzolásos hisztogram 21 képkockája helyett 75 képkocka készült; az oszlopadatok továbbra is valódi, legfrissebb mérési minták, köztes értékek kitalálása nélkül. Ez nem a fizikai érzékelő vagy a monitor hardveres késleltetésének mérése.

## Indítás és megjelenítés

- Tiszta Windows-másolatban, szóközt és ékezetet tartalmazó útvonalról, másik munkakönyvtárból létrejött a venv, települtek a függőségek, és a `--check-env` a helyi venv interpreterét jelentette.
- Második indításkor nem történt új telepítés. Másik projekt venv-interpreterével indítva is a célprojekt saját venv-je futott.
- Angol Windows-konzol CP1252 kódolását szimulálva is sikeres az indítás; az indító és az interpreterlekérdezés kimenete explicit UTF-8. Ezt külön subprocess-regressziós teszt ellenőrzi.
- Ubuntu alatt a `start.sh --check-env` létrehozta a `.venv-linux` környezetet és telepítette a függőségeket. Ismételt indításkor a meglévő környezetet használta.
- A két korábbi GUI-belépési pont `--check-env` kapcsolóval ugyanazt a projekt-venv-et használta. A soros monitor `--help` parancsa és a Windows venv `pip check` ellenőrzése sikeres.
- Windows alatt futó demóméréssel, 150%-os asztali skálázásnál képi ellenőrzés történt a világos és fekete témán, Histogram és Waterfall nézeten, összecsukott oldalsávval és működő diagram-eszköztárral.
- Linux alatt 150%-os Tk-skálázással, Xvfb kijelzőn mindkét téma és mindkét diagramnézet renderelése sikeres volt; a világos hisztogram és a fekete waterfall képe vizuálisan is ellenőrizve.
- A CI Linux-környezete rögzítetten `ubuntu-22.04`, ahol a Python 3.9 és 3.12 egyaránt elérhető; az újabb `ubuntu-latest` képekre való automatikus átállás így nem szünteti meg a legrégebbi támogatott Python tesztjét.

## A teszt határa

Valódi AS7265x/Arduino Nano eszközzel és USB-s soros adapterrel nem történt mérés vagy feltöltés. A kommunikációt szimulált porttal, Linux pszeudoterminállal, a beépített demóval és a tényleges firmware-kódot futtató virtuális I²C-harness-szel ellenőriztük. A konkrét panelen még ellenőrizni kell a 3,3 V-os szintillesztést, a LED-ek tényleges bekötését/terhelhetőségét, a konverziós sebességet és a Nano bootloader-profilját.
