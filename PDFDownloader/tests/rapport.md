# Test-rapport for PDFDownloader

## Oversigt
- Test resultater
- Kode kvalitet
	- Navngivningskonventioner
	- Let at forst�/vedligeholde?
	- Fejlh�ndtering
- Testd�kning og evt. forbedringer
- Kommentarer vedr�rende fejl/ineffektivitet

## Test resultater
### Excel l�ser
- `test_excel_reader` - Funktionen `xlsx_chunk_reader.read_xlsx_in_chunks` kan ikke l�se hele excel filen, den fejler efter chunk nr. 6 med en exception fra pandas.

- `test_excel_reader` - Excel filen �bnes p� ny, hver gang der skal l�ses en del af den. �bningen tager ca. 2 sekunder,
s� for 21K r�kker tager det 42 sekunder at l�se filen.

### Downloader
- `test_corrupted_download` - Korrupte filer slettes ikke korrekt, der pr�ves en `unlink` p� en �ben fil.
- `test_needs_user_agent` - Mange hjemmesider kr�ver en user-agent.
- `test_redirect_with_cookie` - Nogle links peger p� en omdirigerings side, der s�tter en cookie. Hvis den ikke findes n�r destinationen n�es, afvises brugeren.
- `test_zerosize_download` - Filer med st�rrelse 0 skal ikke gemmes.
- `test_ssl_cert_error` - En del links i Excel filerne har ugyldige SSL certifikater, som resulterer i afvisning af downloads. Deaktivering af SSL l�ser dette.
- `test_unsupported_encryption` - PyPDF2 kr�ver `pycryptodome` for at kunne �bne filer med AES kryptering. Hvis det ikke er installeret, fejler �bningen og en gyldig fil slettes.
- `test_url_no_scheme` - En del links mangler `http://` eller `https://` i Excel filerne. Disse links ignorers, selvom de er gyldige.

### Status fil
Blev brugt til at blive bekendt med pytest, kan ignoreres.


## Kode kvalitet
### Navngivningskonventioner
- God ensartet navngivning af funktioner og variabler.

### Organisering
- Status- og ui relateret funktioner i `downloader.py` burde ligge i deres egne filer.
- Nogle filer i projektet findes ikke, som fx. `logs/__init__.py`.

### Let at forst�/vedligeholde?
- Veldokumenteret kode, og logikken er let at f�lge.
- Blandet brug af `Thread` og `ThreadPoolExecutor` virker lidt mist�nkeligt.


### Fejlh�ndtering
- Grundig h�ndtering af fejl i koden, og alle fejl logges.
- Der er n�sten for meget logging.
	- Downloads at 10 pdf filer producerer 102kb log filer
		- For de 21057 filer i den mindste excel fil, vil dette resultere i ca. 215mb log filer.
	- Dobbelt-logging af status i flere log-filer og i den endelige Excel fil.
	- Alm. fremgang i downloads logges ogs�; er ikke sikker p� hvad det skal/kan bruges til.


## Testd�kning og evt. forbedringer
- Mangler pt. integrations tests mellem downloader og excel-fil.
- Sv�rt at d�kke alle grene i funktionerne, da der er mange af dem. D�kker kun 53% pt.
- Smid min `mock_server` i skralderen, og brug alm. mocking.
	- Tests er afh�ngig af at min server k�rer, som er et problem.


## Kommentarer vedr�rende fejl/ineffektivitet
- L�sning af Excel fil fejler, s� alle filer vil aldrig blive downloadet.
	- �bning af Excel ved hvert kald g�r funktionen langsom.
	- Testen for at t�lle r�kkerne vil tage ca. 42 sekunder at gennemf�re.
	- Det tager pt. ca 11 sekunder for at t�lle til 7000 ud af 21057.
- Mange flere filer kan downloads ved at rette de fundne fejl.


## Forbedringsforslag
- Brug af threads til downloads, med sammenlagt 90 sekunders timeout i HEAD/GET, resulterer i tr�de der st�r stille og ikke laver noget.
	- Tog 3 minutter for at hente 10 filer.
