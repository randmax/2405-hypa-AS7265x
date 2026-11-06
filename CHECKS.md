# Ellenőrzési jegyzőkönyv – 2026-11-06

## Automatizált ellenőrzések

| Környezet | Eredmény |
|---|---|
| Windows, Python 3.12.10, Matplotlib 3.10.1, NumPy 2.2.5 | 21 teszt: 20 sikeres, 1 Linux-specifikus PTY teszt kihagyva |
| Windows, Python 3.9.13, Matplotlib 3.9.4, NumPy 2.0.2 | 21 teszt: 20 sikeres, 1 Linux-specifikus PTY teszt kihagyva |
| Ubuntu 22.04 / WSL, Python 3.10.12, Matplotlib 3.10.9, NumPy 2.2.6, Tk / Xvfb | Mind a 21 teszt sikeres, a pyserial Linux PTY adatfogadással együtt |

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

Valódi AS7265x/Arduino eszközzel és USB-s soros adapterrel nem történt mérés. A kommunikációt szimulált porttal, Linux pszeudoterminállal és a beépített demóval ellenőriztük. A tényleges firmware baudját, csatornasorrendjét és az USB-eszköz Linux-jogosultságait a konkrét hardveren is ellenőrizni kell.
