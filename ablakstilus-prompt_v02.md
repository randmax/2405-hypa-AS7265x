# Újrahasználható ablakstílus-prompt (v02)

Az alábbi prompt önállóan is használható egy másik alkalmazás felületének elkészítéséhez. Az első mondatban add meg az alkalmazás nevét és feladatát. A színértékek az NNHSpect jelenlegi világos és fekete témájából származnak.

---

Készítsd el vagy alakítsd át az **[ALKALMAZÁS NEVE ÉS FELADATA]** ablakait az alábbi egységes megjelenési és működési szabályok szerint. Használd a projekt meglévő felületi keretrendszerét. A stílus vonatkozzon a főablakra, a külön megnyitható szerkesztőkre, az eszközablakokra és a párbeszédablakokra is.

## Vizuális karakter és tipográfia

- Rendezett, tömör asztali munkafelületet készíts, tompított kékesszürke világos és sötét palaszínű fekete témával.
- Használj egységes, lapos felületeket, finom 1 px-es kereteket és enyhén lekerekített sarkokat.
- Az alap betűtípus **Segoe UI**, tartalék betűtípus sans-serif. Az általános feliratozás 12 logikai px, a kiemelt képi fejlécek 14 px méretűek legyenek.
- A szekciófejlécek és gombfeliratok 600-as, a kisméretű kiemelt címkék 700-as betűsúlyt használjanak. A másodlagos információ a `muted` színt kapja.
- A külső margó általában 16–20 px, a kapcsolódó vezérlők közötti tér 6–10 px legyen. A gombok és beviteli mezők igazodjanak közös sorokhoz.
- A méretek logikai pixelek legyenek; a felület kövesse a képernyő DPI-skálázását.

## Pontos színpaletta

Központi tématáblából dolgozz. Ugyanazok a szemantikus tokenek szabályozzák az összes ablakot és vezérlőt.

| Token / szerep | Világos téma | Fekete téma |
|---|---|---|
| `window` – ablak háttér | `#dce3eb` | `#202735` |
| `text` – elsődleges szöveg | `#24334b` | `#e0e7f0` |
| `accent` – kiemelés | `#355ccc` | `#8eb2ff` |
| `muted` – másodlagos szöveg | `#5d6c82` | `#a4b3c7` |
| `border` – panel- és táblázatkeret | `#b5c3d4` | `#45546a` |
| `panel` – panel háttér | `#edf1f5` | `#293445` |
| `button` – normál gomb | `#e2e9f2` | `#35445b` |
| `input_border` – mező- és gombkeret | `#aebfd2` | `#556a85` |
| `hover_border` – rámutatási keret | `#466ce7` | `#779cff` |
| `hover` – rámutatási háttér | `#cfddf3` | `#405779` |
| `checked` – bekapcsolt vezérlő | `#c3d6f2` | `#365781` |
| `disabled_text` – inaktív szöveg | `#98a3b5` | `#78869a` |
| `disabled` – inaktív háttér | `#d9e0e8` | `#263040` |
| `disabled_border` – inaktív keret | `#dce2ec` | `#374459` |
| `input` – beviteli mező | `#f5f7fa` | `#1e2938` |
| `popup_selection` – menüpont / választóelem kijelölése | `#c3d6f2` | `#405779` |
| `base` – lista / táblázat alap | `#edf2f7` | `#263244` |
| `grid` – táblázatrács | `#d3dce8` | `#3b4b62` |
| `selection` – kijelölt sor | `#bdd1ef` | `#405f8a` |
| `selection_text` – kijelölt sor szövege | `#24334b` | `#ffffff` |
| `header` – szekció-, fül- és táblázatfejléc | `#c7d4e5` | `#354761` |
| `header_text` – fejléc szövege | `#344d70` | `#c5d6ed` |
| `splitter` – elválasztó / átméretező fogantyú | `#afbed1` | `#45546a` |
| `menu` – menüsor és menü | `#c7d4e5` | `#182130` |
| `status` – státuszsor | `#c7d4e5` | `#182130` |
| `scroll_track` – görgetősáv pálya | `#d5dee9` | `#202c3d` |
| `scroll_handle` – görgetősáv fogantyú | `#8c9fb9` | `#607a9a` |
| `image_background` – kép / adathiány háttere | `#c4cfdd` | `#162235` |
| `histogram` – diagramfelület | `#e8eef5` | `#233044` |
| `axis` – diagramtengely | `#97a3b5` | `#6f86a3` |
| `axis_text` – tengelyfelirat | `#66758e` | `#b3c7df` |
| `tooltip` – buboréksúgó háttér | `#ffffff` | `#354761` |

Az elsődleges művelet gombja mindkét témában `#466ce7` háttérrel, fehér felirattal és azonos színű kerettel jelenjen meg. Rámutatáskor a háttér `#3556ca` legyen. A folyamatjelző kitöltése szintén `#466ce7`.

## Gombok és mezők

- Normál gomb: `button` háttér, `text` felirat, 1 px `input_border` keret, 6 px sarokkerekítés, függőlegesen 8 px és vízszintesen 10 px belső tér.
- Rámutatáskor: `hover` háttér és `hover_border` keret. Bekapcsolt állapotban: `checked` háttér. Az állapotváltások tartsák meg a vezérlő méretét.
- Az elsődleges művelet kapja a fenti kék gombstílust. A többi művelet a normál gombstílust használja.
- A képekhez és listákhoz tartozó kisebb eszközgombok 3 px függőleges, 9 px vízszintes belső teret és 5 px sarokkerekítést kapjanak.
- A letiltott vezérlők a `disabled`, `disabled_text` és `disabled_border` tokeneket használják.
- Beviteli mező és legördülő választó: `input` háttér, 1 px `input_border` keret, 5 px sarokkerekítés, 5 px belső tér, legalább 22 px tartalommagasság.
- A számmezők jobb szélén legyen jól látható fel/le léptetőnyíl. Ezek háttere `header`, rámutatási háttere `checked`. Mindkét témában olvasható ikonokat használj.
- A billentyűzetfókusz legyen felismerhető. A fókusz megjelenítése se mozdítsa el a környező vezérlőket.
- A fülek fejléce `header` hátteret és `header_text` szöveget kapjon, 9 × 14 px belső térrel. Az aktív fül `checked` hátteret, `text` feliratot és 2 px-es alsó `accent` jelölést használjon.
- A táblázatok 5 px-es sarokkerekítést, `base` hátteret, `grid` rácsot és egységes kijelölést kapjanak. A fejlécek belső tere 6 px legyen.
- A görgetősávok 12 px vastagok, a fogantyúk 4 px sugarúak és legalább 24 px hosszúak legyenek.

## Kötelező témaválasztó menü

- A fő menüsoron legyen **Téma** menü, benne **Világos** és **Fekete** választással.
- A két menüpont kölcsönösen kizáró, pipával jelzett választás legyen. Az alapértelmezett téma a Világos.
- A témaváltás azonnal érvényesüljön minden már megnyitott ablakban, párbeszédablakban, oldalsávban, táblázatban, menüben, súgóban és diagramon.
- Az újonnan megnyíló ablakok az aktuális témát örököljék.
- A témaváltás őrizze meg a mezők értékét, a kiválasztást, a görgetési helyet, a képek zoomját, a panelarányokat és a felhasználó által beállított ablakméretet.
- PySide6/Qt esetén közös `QPalette` és központi stíluslap kezelje a vezérlőket; a saját rajzolású képek és diagramok is ugyanebből a palettából kapják a felületi színeket.

## Oldalsávok és összecsukható szekciók

- Az oldalsáv tartalmát logikus, külön-külön összecsukható szekciókra bontsd.
- A szekció teljes fejlécére lehessen kattintani. A fejlécben nyíl jelezze az állapotot: nyitva lefelé, összecsukva jobbra mutasson.
- A szekció `panel` hátteret, 1 px `border` keretet és 9 px sarokkerekítést kapjon. A belső margó megközelítőleg 10 px, a fejléc és a tartalom között 8 px tér legyen.
- A szekciófejléc `header` hátteret, `header_text` feliratot, 5 px sarokkerekítést és 6 px belső teret használjon.
- Összecsukáskor csak a tartalom láthatósága változzon. Az értékek, kijelölések és a tartalom belső állapota maradjon meg.
- Az oldalsáv jellemző szélessége 280–320 px legyen. Sok vezérlőnél a tartalma függőlegesen görgethető legyen.
- A hosszú listák és metaadatpanelek kapjanak belső görgetést. Ha kézzel állítható a magasságuk, az átméretező fogantyú a panelen belüli területet módosítsa.
- Szekció nyitása/zárása és lista átméretezése közben a főablak külső mérete maradjon stabil; a rendelkezésre álló belső hely és a görgetősáv igazodjon a tartalomhoz.

## Stabil elrendezés változó szövegnél

**A változó státuszszöveg, fájlnév, mért érték vagy folyamatjelzés ne okozzon folyamatos ablakátméretezést, ugráló paneleket vagy elmozduló gombokat.**

- A felhasználó által beállított ablakméret és panelarány legyen a kiindulópont. Az új szöveg a számára kijelölt helyen jelenjen meg.
- A rendszeresen változó feliratoknak előre foglalj megfelelő szélességet és stabil, például 2–3 sornyi magasságot. A sorok számának változása ezen a területen belül történjen.
- A hosszú fájlnevet és elérési utat szükség esetén rövidítsd ellipszissel; a teljes szöveg buboréksúgóban vagy részletes adatpanelen legyen elérhető.
- A hosszú magyarázat korlátozott magasságú, görgethető vagy külön összecsukható területen jelenjen meg.
- A tördelhető felirat a panel rendelkezésre álló szélességéhez igazodjon. Egy hosszú szó vagy fájlnév se növelje meg automatikusan az ablak minimális szélességét.
- A folyamatjelző és a megszakításgomb számára előre lefoglalt sor legyen. Ha ezek rövid időre eltűnnek, a környező tartalom ne ugráljon.
- Szövegfrissítéskor ne hívd újra az ablak `adjustSize()` vagy `resize()` műveletét, és ne számíts új ablak-minimumméretet minden értékváltozásnál.
- PySide6/Qt esetén használj megfelelő `QSizePolicy` beállításokat, korlátozott méretű szövegterületeket, elrendezéseket és görgethető oldalsávot. A folyamatjelző helyét például `setRetainSizeWhenHidden(True)` is megőrizheti.
- Ablakméret-változáskor a belső tartalom igazodjon a felhasználó műveletéhez. Az alkalmazás ne állítsa vissza önkényesen a korábbi ablakméretet, zoomot vagy görgetési helyet.

## Görgővel csak kattintás után lehessen értéket állítani

**A puszta rámutatás és a billentyűzettel kapott fókusz önmagában ne engedélyezze egy értékmező görgős módosítását.**

- A számmező vagy legördülő választó csak akkor reagálhat értékváltoztatással a görgőre, ha a felhasználó előtte bal egérgombbal belekattintott, és az a mező még fókuszban van.
- Ez a mező belső szövegszerkesztőjére és léptetőgombjaira kattintáskor is következetesen működjön.
- Az engedélyezés mezőnként történjen. Egy mezőre kattintás ne aktiválja a többi mező görgős állítását.
- Fókuszvesztéskor szűnjön meg a görgős értékállítás engedélye. Az újabb billentyűzetfókusz után ismét kattintás szükséges hozzá.
- A menüsor, szekciófejléc vagy oldalsáv fölötti görgetés ne változtassa meg egy mögötte vagy korábban aktív mező értékét.
- Inaktív mező fölött a görgő a görgethető szülőpanel navigációját szolgálja; a mező aktuális értéke maradjon meg.
- A képek és diagramok saját, kifejezetten tervezett görgős zoomja továbbra is a képi navigációhoz tartozik.
- PySide6/Qt esetén alkalmazásszintű eseményszűrővel kezeld a `QAbstractSpinBox` és `QComboBox` vezérlőket, a gyermekmezőikkel együtt. Külön állapot jelezze a tényleges kattintást; a `hasFocus()` feltétel önmagában kevés. A szabály az eszköz- és párbeszédablakokra is vonatkozzon.

## Képi és adatréteges nézetek, ha vannak az alkalmazásban

- A képfelület háttere az `image_background` token legyen, a diagramoké a `histogram` token. A tengelyek és felirataik a megfelelő témaszíneket használják.
- Raszteres réteg kijelölését enyhe, körülbelül 10–12%-os világosítással jelezd a réteg saját, érvényes pixelein.
- A kijelölés kövesse a kép tényleges alakját és átlátszósági maszkját. Ne rajzolj köré általános téglalapot vagy más, az adathatártól eltérő körvonalat.
- A fényerőjelzés a megjelenítés része legyen: a forrásadatot, az alfa/nodata maszkot és a mentett adatértékeket őrizze meg.
- Rétegváltás, témaváltás és megjelenítési mód váltása közben a felhasználó által beállított képi nézet maradjon stabil.

## Átvételi ellenőrzések

1. Válts Világos és Fekete téma között több megnyitott ablaknál; minden felületi elem igazodjon az aktív témához.
2. Csukd össze és nyisd ki az oldalsáv szekcióit; az értékek és a főablak mérete maradjon meg.
3. Váltogass rövid és hosszú státuszszövegeket, fájlneveket és számlálóértékeket; az ablak és a szomszédos gombok ne ugráljanak.
4. Görgess egy számmező vagy választó fölött kattintás nélkül, majd csak billentyűzetfókusz után; az érték maradjon változatlan.
5. Kattints a mezőbe, majd görgess; az érték most állítható legyen. Fókuszvesztés után szűnjön meg ez a lehetőség.
6. Görgess a menüsor, egy szekciófejléc és egy hosszú oldalsáv fölött; a mezőértékek maradjanak meg.
7. Próbáld ki kisebb ablakméretnél és nagyított DPI mellett is: az összes funkció elérhető legyen, és a tartalom a saját helyén tördelődjön vagy görgetődjön.

Az elkészült felületet működés közben és képen is ellenőrizd mindkét témával, rövid és hosszú feliratokkal.

---

## Verzió és alkalmazási sorrend

- **Verzió:** v02, 2026-11-06. Előzmény: `ablakstilus-prompt_v01.md` (változatlanul megőrzendő).
- A v02 az eredeti teljes stílusszabályt megőrzi, és az alábbi futási, teljesítmény- és hordozhatósági direktívákkal egészíti ki. Keretrendszerbeli eltérés esetén az alábbi pontosítások érvényesek.

## Optimalizált megjelenítés

- A mérési adatfogadás és a képernyőfrissítés legyen egymástól független. Az összes érvényes mintát dolgozd fel, de a megjelenítést alapértelmezetten legfeljebb **10 képkocka/s** gyakorisággal frissítsd. Új adat vagy felhasználói változtatás nélkül ne rajzolj újra.
- A diagram tengelyeit, oszlopait, képrétegét és színskáláját egyszer hozd létre nézetenként. Frissítéskor a meglévő objektumok adatait változtasd; ne töröld és építsd újra a teljes ábrát minden mintánál.
- Egy eseményköri frissítés dolgozzon fel korlátozott adag adatot (például legfeljebb 200 eseményt / 8 ms-ot), majd adja vissza a vezérlést a felületnek. A tényleges festést összevonva, az eseménykörön keresztül ütemezd (`draw_idle`, illetve a keretrendszer megfelelője).
- Az átlagot gördülő összegből számítsd; a korlátozott méretű puffer elejéről ne távolíts el listás `pop(0)` művelettel. A waterfall csak a látható, legutolsó sorokat alakítsa képpé.
- A naplót adagokban frissítsd, legfeljebb 2000 látható sorral. A felhasználó által visszagörgetett napló ne ugorjon automatikusan az aljára.
- Témaváltás ne építse újra a felületet vagy a diagramot. Őrizze meg a tengelyhatárokat, a mezőértékeket, az ablakméretet, a panelosztást, az összecsukott szekciókat és a görgetési helyet.
- A nagyítás és az eltolás kapcsolja ki az automatikus tengelykövetést; egyértelmű „Nézet alaphelyzetbe” művelet kapcsolja vissza. Megjelenítési módonként őrizd meg a kézzel beállított nézetet.
- A DPI-skálázást egyszer állítsd be indításkor. A platformon elérhető Segoe UI, DejaVu Sans vagy más olvasható sans-serif betűtípust használd. Nagyított DPI mellett se legyen levágott vagy elérhetetlen vezérlő.

## Optimalizált futás és erőforrás-kezelés

- Soros port megnyitása és olvasása külön, megszakítható munkaszálon történjen, rövid, korlátozott olvasási időtúllépéssel. Háttérszál soha ne módosítson közvetlenül GUI-vezérlőt.
- A munkaszál és a felület közti eseménysor legyen korlátozott (például 512 elem), megállításkor is megszakítható visszanyomással. A méréspuffer mérete legyen ellenőrzött, konfigurálható és véges (például 1–10000 minta); a waterfall magassága is legyen korlátozott.
- A részleges sorokat gyűjtsd össze; egy sor több olvasási blokkban is érkezhet. A túl hosszú vagy hibás sort hagyd ki, utána álljon helyre a feldolgozás. Csak a várt csatornaszámú, véges számokból álló sor kerüljön a mérési pufferbe.
- Ne hozz létre többszörös időzítőt vagy párhuzamos portolvasót ismételt indításkor. Leállításkor és ablakbezáráskor állítsd le a munkaszálat, zárd le a portot és szüntesd meg az időzített munkát.
- Ne használj aktív várakozást, végtelen méretű listát vagy korlátlan naplózást. Üresjáratban az eseménykör csak ritkán ébredjen fel; hálózati művelet csak az első függőségtelepítéshez vagy megváltozott követelményekhez kelljen.
- Leállítás után is lehessen CSV-be menteni. A CSV a pufferben őrzött eredeti mérési értékeket tartalmazza, UTF-8 kódolással, nem a megjelenítésből visszaszámolt adatokat. Új méréskor egyértelmű legyen a puffer újrakezdése.

## Automatikus venv-indítás Windows és Linux alatt

- Adj standard könyvtárra épülő indítót és platformonként kényelmes belépési pontot (`start.py`, `start.bat`, `start.sh`). A korábbi közvetlen Python-belépési pontok is ugyanazt az automatikus venv-indítót használják, a külső csomagok importálása előtt.
- Az indító az elérési útját a saját fájljából számítsa, ne az aktuális munkakönyvtárból. Szóközt és ékezetet tartalmazó útvonalról, illetve másik könyvtárból indítva is működjön. Alfolyamatot argumentumlistával, `shell=False` mellett futtass.
- Windows alatt a projekt `.venv/Scripts/python.exe`, Linux alatt a `.venv-linux/bin/python` interpreterével fusson az alkalmazás. A külön könyvtárak akadályozzák meg a Windows/Linux közös munkapéldány venv-jeinek ütközését. Más projekthez tartozó aktív venv esetén is a helyi környezetet válaszd.
- Hiányzó környezetet automatikusan hozz létre `venv` segítségével, majd kizárólag ebbe telepíts `python -m pip install -r requirements.txt` paranccsal. Meglévő, érvénytelen környezetet ne törölj automatikusan: adj érthető helyreállítási útmutatót.
- Függőségeket csak első indításkor, megváltozott követelményfájl vagy hiányzó csomag esetén telepíts. A követelményfájl ujjlenyomatát csak sikeres telepítés után jegyezd fel. Ne frissíts minden indításkor, és ne módosíts globális Python-csomagokat.
- Nem kell kézzel aktiválni a venv-et. Ne kérj PowerShell execution-policy módosítást, és ne futtasd rendszergazdaként a programot. Az interpreter közvetlen indítása elegendő.
- A Tk és a venv rendszerfüggőségeire adj célzott üzenetet: Debian/Ubuntu `python3-tk python3-venv`, Fedora `python3-tkinter`. Rendszercsomagok és eszközjogosultságok módosítása legyen dokumentált, kézi telepítési lépés.
- Linuxon kezeld a `/dev/ttyUSB*`, `/dev/ttyACM*` és `/dev/serial/by-id/*` neveket, és engedd a port kézi megadását is. Hozzáférési hibánál utalj a disztribúció szerinti `dialout` / `uucp` csoportra; ne javasolj általános `chmod 777` használatot.
- Grafikus munkamenet nélkül adj érthető DISPLAY/Wayland/X11 hibát. Legyen GUI nélküli `--check-env` ellenőrzés, és hardver nélkül is használható `--demo` mód.
- A `.venv`, `.venv-linux`, mérési CSV-k és generált ellenőrzési állományok kerüljenek `.gitignore` alá; ne tölts fel platformfüggő venv-et a forráskód mellé.

## A meglévő keretrendszer következetes használata

- Tkinter esetén központi `ttk.Style`, szemantikus paletta és a klasszikus Tk-vezérlők regisztere biztosítsa a témázást. A már létező legördülő listákat, Matplotlib-diagramot, színskálát és saját párbeszédablakokat is frissítsd.
- A Tk/ttk natívan támogatott geometriai és tipográfiai lehetőségeit használd. A pixelpontos sarokkerekítés és a 600-as betűsúly helyett elfogadható a lapos, finom keretezett felület és félkövér kiemelés. Kizárólag ezekért ne cseréld le a keretrendszert, és ne vezess be drága egyedi rajzolást.
- Az operációs rendszer által kezelt címsor és natív fájlválasztó a rendszer megjelenését követheti. Az alkalmazás saját ablakai és párbeszédablakai minden esetben a kiválasztott témát használják.
- A görgővédelem a vezérlő osztálykötése előtt fusson. Windows `<MouseWheel>` és Linux `<Button-4>/<Button-5>` eseményekre egyaránt ellenőrizd a tényleges kattintási engedélyt és annak fókuszvesztéskori törlését.

## Kiegészített átvételi ellenőrzések

8. Tiszta projektmásolatból, venv nélkül indítsd Windows és Linux alatt; az alkalmazás saját venv-interpretere fusson. Második indításkor változatlan függőségekkel ne legyen telepítés.
9. Indítsd el másik könyvtárból, szóközös/ékezetes útvonalról és idegen aktív venv mellett is. Hiányzó Tk, hibás venv és hiányzó DISPLAY esetén legyen használható hibaüzenet.
10. Küldj nagy sebességgel teljes és darabolt sorokat, hibás csatornaszámot, fejlécet, NaN/Inf értéket és túl hosszú sort. A felület maradjon kezelhető, a memória és a frissítési gyakoriság korlátozott.
11. Ellenőrizd a hisztogram átlagát, a waterfall időirányát és a CSV értékeit ismert mintákkal. Témaváltás és új adat után a kézzel rögzített nézet ne változzon.
12. Ismételd meg az indítás–leállítás ciklust, bontsd a kapcsolatot, majd zárd be az ablakot mérés közben. Ne maradjon nyitott port vagy több adatolvasó.
13. Képen és működés közben is ellenőrizd mindkét témát, a kis ablakméretet és a nagyított DPI-t. Külön jelezd, mely ellenőrzés történt demóval, tesztporttal vagy valódi hardverrel.
