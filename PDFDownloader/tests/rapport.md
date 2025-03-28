# Test-rapport for PDFDownloader

## Oversigt
- Test resultater
- Kode kvalitet
	- Navngivningskonventioner
	- Let at forstå/vedligeholde?
	- Fejlhåndtering
- Testdækning og evt. forbedringer
- Kommentarer vedrørende fejl/ineffektivitet

## Test resultater
### Excel læser
- `test_excel_reader` - Funktionen `xlsx_chunk_reader.read_xlsx_in_chunks` kan ikke læse hele excel filen, den fejler efter chunk nr. 6 med en exception fra pandas.

- `test_excel_reader` - Excel filen åbnes på ny, hver gang der skal læses en del af den. Åbningen tager ca. 2 sekunder,
så for 21K rækker tager det 42 sekunder at læse filen.

### Downloader
- `test_corrupted_download` - Korrupte filer slettes ikke korrekt, der prøves en `unlink` på en åben fil.
- `test_needs_user_agent` - Mange hjemmesider kræver en user-agent.
- `test_redirect_with_cookie` - Nogle links peger på en omdirigerings side, der sætter en cookie. Hvis den ikke findes når destinationen nåes, afvises brugeren.
- `test_zerosize_download` - Filer med størrelse 0 skal ikke gemmes.
- `test_ssl_cert_error` - En del links i Excel filerne har ugyldige SSL certifikater, som resulterer i afvisning af downloads. Deaktivering af SSL løser dette.
- `test_unsupported_encryption` - PyPDF2 kræver `pycryptodome` for at kunne åbne filer med AES kryptering. Hvis det ikke er installeret, fejler åbningen og en gyldig fil slettes.
- `test_url_no_scheme` - En del links mangler `http://` eller `https://` i Excel filerne. Disse links ignorers, selvom de er gyldige.

### Status fil
Blev brugt til at blive bekendt med pytest, kan ignoreres.


## Kode kvalitet
### Navngivningskonventioner
- God ensartet navngivning af funktioner og variabler.

### Organisering
- Status- og ui relateret funktioner i `downloader.py` burde ligge i deres egne filer.
- Nogle filer i projektet findes ikke, som fx. `logs/__init__.py`.

### Let at forstå/vedligeholde?
- Veldokumenteret kode, og logikken er let at følge.
- Blandet brug af `Thread` og `ThreadPoolExecutor` virker lidt mistænkeligt.


### Fejlhåndtering
- Grundig håndtering af fejl i koden, og alle fejl logges.
- Der er næsten for meget logging.
	- Downloads at 10 pdf filer producerer 102kb log filer
		- For de 21057 filer i den mindste excel fil, vil dette resultere i ca. 215mb log filer.
	- Dobbelt-logging af status i flere log-filer og i den endelige Excel fil.
	- Alm. fremgang i downloads logges også; er ikke sikker på hvad det skal/kan bruges til.


## Testdækning og evt. forbedringer
- Mangler pt. integrations tests mellem downloader og excel-fil.
- Svært at dække alle grene i funktionerne, da der er mange af dem. Dækker kun 53% pt.
- Smid min `mock_server` i skralderen, og brug alm. mocking.
	- Tests er afhængig af at min server kører, som er et problem.


## Kommentarer vedrørende fejl/ineffektivitet
- Læsning af Excel fil fejler, så alle filer vil aldrig blive downloadet.
	- Åbning af Excel ved hvert kald gør funktionen langsom.
	- Testen for at tælle rækkerne vil tage ca. 42 sekunder at gennemføre.
	- Det tager pt. ca 11 sekunder for at tælle til 7000 ud af 21057.
- Mange flere filer kan downloads ved at rette de fundne fejl.


## Forbedringsforslag
- Brug af threads til downloads, med sammenlagt 90 sekunders timeout i HEAD/GET, resulterer i tråde der står stille og ikke laver noget.
	- Tog 3 minutter for at hente 10 filer.
