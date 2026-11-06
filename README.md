# AS7265x spektrális adatgyűjtő

Tkinter / Matplotlib alkalmazás az AS7265x 18 csatornás soros mérési adatainak megjelenítésére Windows és Linux alatt. Világos és Fekete téma, élő vagy átlagolt hisztogram, waterfall, méretezhető adatnapló és CSV-export.

## Indítás

Python **3.9+** szükséges, Windows alatt a Tcl/Tk komponenssel. Az első indításhoz internet és a projektmappa írási joga kell. Az indító létrehozza a helyi venv-et, telepíti a `requirements.txt` függőségeit, majd annak Pythonjával futtatja a programot. Később csak változott követelmények vagy hiányzó csomag esetén telepít újra. Nem kell aktiválni a környezetet, sem PowerShell execution-policy beállítást módosítani.

**Windows:** indítsd a `start.bat` fájlt, vagy:

```powershell
py -3 start.py
py -3 start.py --demo
py -3 start.py --check-env
```

**Debian / Ubuntu:** a rendszerfüggőségeket egyszer telepítsd:

```sh
sudo apt install python3-tk python3-venv
sh start.sh
sh start.sh --demo
sh start.sh --check-env
```

Fedora alatt a Tk csomagja `python3-tkinter`. Grafikus X11/Wayland munkamenet szükséges; a `--check-env` kijelző nélkül is működik. A `python3 start.py`, valamint a korábbi `mySpectRead01.py` és `mySpectRead02.py` belépési pontok is automatikusan venv-ben indítanak. Az indító másik munkakönyvtárból is hívható a teljes elérési útjával.

Windows alatt `.venv`, Linux alatt `.venv-linux` készül. Így közös Windows/WSL projektmappából is külön környezetet használ a két rendszer. A venv nem másolható át másik operációs rendszerre. Ha egy meglévő környezet hibás vagy a Pythonját eltávolították, zárd be az alkalmazást, nevezd át az érintett venv-mappát, majd indíts újra.

## Mérés és adatformátum

1. Frissítsd a portlistát, és válassz portot. Kézzel is beírható például `COM3`, `/dev/ttyUSB0`, `/dev/ttyACM0` vagy egy `/dev/serial/by-id/…` útvonal.
2. Állítsd be a firmware-rel egyező baudot (alapérték: 115200) és a puffer méretét (1–10000 minta).
3. Indíts mérést. A **demó** szimulált adatot használ, eszköz nélkül.
4. Válaszd a Histogram vagy Waterfall nézetet a Megjelenítés szekcióban. A hisztogram alapból **a legfrissebb teljes mintát mutatja mind a 18 csatornán**. Az **Átlagolás (minta, 1 = élő)** külön állítható: 1 az azonnali élő nézet, nagyobb érték az utolsó ennyi elérhető minta átlaga. Az előzménypuffer mérete önmagában nem lassítja a hisztogramot.
5. A waterfall magassága 1–2000 sor, de legfeljebb a pufferben őrzött minták látszanak. A legrégebbi sor felül, a legújabb alul jelenik meg. Az átlagolás a hisztogramra vonatkozik; a waterfall az eredeti mintákat mutatja.
6. A CSV az utolsó N minta eredeti értékeit menti; leállítás után is elérhető. **Új mérés új puffert kezd**, ezért a megőrzendő adatot előbb mentsd el.

Nagy átlagolási ablak tudatosan lassítja a változások követését. Például 50 minta és 2 Hz-es mérés esetén a teljes ablak cserélődése körülbelül 25 másodperc. Gyors visszajelzéshez hagyd az átlagolást 1-en; a CSV előzménypuffere ettől továbbra is lehet nagy.

A firmware soronként 18 vesszővel elválasztott számot küldjön, LF vagy CRLF lezárással. A sor végén egy záró vessző megengedett. A csatornák sorrendje:

```text
410,435,460,485,510,535,560,585,610,645,680,705,730,760,810,860,900,940 nm
```

A program a fejlécet, a hibás elemszámú, nem véges (NaN/Inf), extrém (`abs(x) > 1e100`) vagy 4096 bájtnál hosszabb sorokat kihagyja. A CSV UTF-8 kódolású, első sora a hullámhosszakat tartalmazza.

Linuxon a porthoz a felhasználónak hozzáférési jog kell. Debian/Ubuntu rendszeren jellemzően a `dialout`, egyes disztribúciókon az `uucp` csoport szolgál erre. Például Debian/Ubuntu alatt `sudo usermod -aG dialout "$USER"`, majd kijelentkezés és visszajelentkezés szükséges. A programot saját felhasználóként indítsd, és zárj be minden más, azonos portot használó soros monitort. WSL alatt az USB-eszközt külön át kell adni a Linux rendszernek; a demó ehhez nem igényel USB-t.

A `test01.py PORT BAUD` egy egyszerű, szintén automatikus venv-indítású konzolos soros monitor.

## Arduino Nano firmware és panelvezérlés

Az új Arduino program: [firmware/AS7265xController](firmware/AS7265xController). Klasszikus **Nano / ATmega328P**, **SDA=A4, SCL=A5** bekötéshez készült. A teljes bekötési, build-, bootloader- és UART-feltöltési leírás: [firmware/README.md](firmware/README.md).

Az új firmware feltöltése és kapcsolódás után a **Nano / szenzor vezérlése** szekcióban elérhető:

- a fehér, IR és UV megvilágító LED külön kapcsolása és 12,5–100 mA közötti árambeállítása;
- mindhárom chip jelző LED-je és annak 1–8 mA-es árambeállítása, ha a panelen ki van építve;
- 1× / 3,7× / 16× / 64× erősítés és 1–256 integrációs ciklus/bank;
- nyers ADC vagy kalibrált adatok, automatikus pufferürítéssel formátum-/expozícióváltáskor;
- az adatküldés szüneteltetése/folytatása nyitott port mellett, külön egyszeri mérés, három hőmérséklet.

A panelparancsok visszaigazolást kapnak. Hibánál a GUI az utolsó visszaigazolt beállítást állítja vissza; a „Minden LED kikapcsolása” elsőbbséget kap a még el nem küldött LED-parancsokkal szemben. A demó a panelvezérlést is szimulálja. A régi CSV-only Arduino program változatlanul olvasható, de a vezérlőelemek azon letiltva maradnak.

A `firmware/releases/nano` és `nano-old` mappában lefordított alkalmazás- és bootloaderes HEX-ek, SHA-256 manifestek találhatók. Normál UART-frissítéshez a meglévő Nano bootloadert és az alkalmazás HEX-et használjuk. A bootloadert tartalmazó egyesített HEX első helyreállításhoz / ISP-programozáshoz való; a bootloader telepítése és a későbbi UART-os programfrissítés külön művelet. Ez az Arduino programjára vonatkozik, az AS7265x gyári firmware-ét nem cseréli.

## Felület és teljesítmény

- A **Téma → Világos / Fekete** választás a teljes saját felületet és a diagramot frissíti. A natív fájlválasztó és az ablak címsora az operációs rendszer témáját követheti.
- Az oldalsáv szekciói összecsukhatók; a diagram és a napló közötti elválasztó húzható. Kis ablakban az oldalsáv görgethető.
- A számmező és a legördülő csak tényleges kattintás és megtartott fókusz után módosítható görgővel; egyébként az oldalsáv gördül.
- A diagram eszköztárával nagyíthatsz és eltolhatsz. Kézi navigáció után kikapcsol az automatikus skálázás. A **Nézet alaphelyzetbe** visszakapcsolja.
- A soros olvasó külön szálon fut, 0,05 s olvasási időtúllépéssel. A teljes minták közvetlenül a szálbiztos, korlátozott előzménypufferbe kerülnek; a GUI annak friss pillanatképét rajzolja, legfeljebb 30 Hz gyakorisággal. A hisztogram a változatlan tengelyek és feliratok helyett csak az oszlopokat festi újra (blitting). A tengelyek kerekített határokat és visszaállítási késleltetést használnak, így a kis ingadozások nem okoznak folytonos teljes újrarajzolást. Téma-, méret-, zoom- és mértékegységváltáskor a háttér újraépül.
- A rajzolás összevonása nem simítja vagy interpolálja a mérési értékeket: a megjelenített oszlopok a legfrissebb teljes spektrumot, illetve a külön beállított átlagot mutatják. A valódi új spektrumok gyakoriságát a Nano kiolvasási sebessége és a szenzor integrációja is korlátozza. Az új firmware 400 kHz I²C-t, rövid regiszter-pollingot és konverzió közben is működő parancsfogadást használ.
- A kapcsolati üzeneteknek külön, 64 elemű sora van. Túl sok diagnosztikai sor esetén ezek összevonódnak; a napló telítődése nem állítja meg az érvényes mérések fogadását. A rajzolás köztes képkockákat kihagyhat, az eredeti méréseket a beállított pufferhatárig őrzi.
- A napló legfeljebb 2000 sort őriz. A nagy adatsebesség nem jelent korlátlan veszteségmentes rögzítést: a soros eszköz és az operációs rendszer bemeneti puffere is véges. Tartós, teljes mérési archívumhoz külön folyamatos fájlírás szükséges.

Az aktuális újrahasználható specifikáció: [ablakstilus-prompt_v02.md](ablakstilus-prompt_v02.md). Az eredeti [v01](ablakstilus-prompt_v01.md) megmaradt. A Tk/ttk a prompt palettáját, lapos kereteit és platformon elérhető betűtípusát alkalmazza; a pixelpontos sarokkerekítés helyett natív ttk-vezérlőket használ.

## Ellenőrzések

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

```sh
# Linux grafikus munkamenetben:
.venv-linux/bin/python -m unittest discover -s tests -v
# Kijelző nélküli teszthez: sudo apt install xvfb xauth
xvfb-run -a .venv-linux/bin/python -m unittest discover -s tests -v
```

A tesztek ellenőrzik a parser hibakezelését, a részleges és túl hosszú sorok feldolgozását, a puffer átlagát és sorrendjét, a CSV-t, a megszakítható háttérszálat, a GUI témaváltását és állapotmegőrzését, a görgővédelmet és az ismételt indítást. Külön regressziós teszt ellenőrzi mind a 18 csatorna azonnali lépcsőválaszát, az előzménytől független átlagolást, a GUI megállása utáni első képkocka frissességét, valamint 5000 spektrum fogadását telt GUI-eseménysor és 2000 diagnosztikai sor mellett. Linuxon valódi pszeudoterminálon keresztül is vizsgálják a pyserial adatfogadását. A GitHub Actions Windows és Linux rendszeren futtatja ugyanezeket.

A ténylegesen lefuttatott helyi ellenőrzések és a hardveres teszt határai: [CHECKS.md](CHECKS.md).
