# Ellenőrzési jegyzőkönyv – 2026-11-06

## Automatizált ellenőrzések

| Környezet | Eredmény |
|---|---|
| Windows, Python 3.12.10, Matplotlib 3.10.1, NumPy 2.2.5 | 16 teszt: 15 sikeres, 1 Linux-specifikus PTY teszt kihagyva |
| Windows, Python 3.9.13, Matplotlib 3.9.4, NumPy 2.0.2 | 16 teszt: 15 sikeres, 1 Linux-specifikus PTY teszt kihagyva |
| Ubuntu 22.04 / WSL, Python 3.10.12, Matplotlib 3.10.9, NumPy 2.2.6, Tk / Xvfb | Mind a 16 teszt sikeres, a pyserial Linux PTY adatfogadással együtt |

Ellenőrzött viselkedés: 18 csatornás parser, záró vessző, NaN/Inf és hibás sorok elutasítása, darabolt sorok összefűzése, túl hosszú sor utáni helyreállás, gördülő átlag, pufferkorlát és sorrend, eredeti adatok CSV-exportja, megszakítás telt eseménysor mellett, portlezárás, ismételt indítás/leállítás, leállítás utáni menthetőség, újrahasznált diagramobjektumok, waterfall időiránya, témaváltás állapotmegőrzéssel, nézetenként megőrzött tengelyhatárok, kattintáshoz kötött görgőkezelés, korlátozott napló, hosszú státuszszöveg, 150%-os skálázásnál a bitmap és a vászon méretének egyezése, témázott buboréksúgó és erőforrás-felszabadítása.

A Python 3.9-hez feloldott Matplotlib/Pillow páros külső `DeprecationWarning` üzenetet adhat a toolbar ikonjainak létrehozásakor; az ellenőrzések ettől sikeresek. A függőségkorlátok mellett a pip a használt Pythonhoz kompatibilis csomagverziókat választja.

## Indítás és megjelenítés

- Tiszta Windows-másolatban, szóközt és ékezetet tartalmazó útvonalról, másik munkakönyvtárból létrejött a venv, települtek a függőségek, és a `--check-env` a helyi venv interpreterét jelentette.
- Második indításkor nem történt új telepítés. Másik projekt venv-interpreterével indítva is a célprojekt saját venv-je futott.
- Ubuntu alatt a `start.sh --check-env` létrehozta a `.venv-linux` környezetet és telepítette a függőségeket. Ismételt indításkor a meglévő környezetet használta.
- A két korábbi GUI-belépési pont `--check-env` kapcsolóval ugyanazt a projekt-venv-et használta. A soros monitor `--help` parancsa és a Windows venv `pip check` ellenőrzése sikeres.
- Windows alatt futó demóméréssel, 150%-os asztali skálázásnál képi ellenőrzés történt a világos és fekete témán, Histogram és Waterfall nézeten, összecsukott oldalsávval és működő diagram-eszköztárral.
- Linux alatt 150%-os Tk-skálázással, Xvfb kijelzőn mindkét téma és mindkét diagramnézet renderelése sikeres volt; a világos hisztogram és a fekete waterfall képe vizuálisan is ellenőrizve.

## A teszt határa

Valódi AS7265x/Arduino eszközzel és USB-s soros adapterrel nem történt mérés. A kommunikációt szimulált porttal, Linux pszeudoterminállal és a beépített demóval ellenőriztük. A tényleges firmware baudját, csatornasorrendjét és az USB-eszköz Linux-jogosultságait a konkrét hardveren is ellenőrizni kell.
