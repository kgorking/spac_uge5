# Test-rapport for PDFDownloader

## Oversigt
- Test resultater
- Kode kvalitet
	- Navngivningskonventioner
		- ensartet, logisk organiseret?
	- Let at forstå/vedligeholde?
	- Fejlhåndtering
- Testdækning og evt. forbedringer
- Kommentarer vedr. fejl/ineffektivitet

## Test resultater
### Excel læser
- `test_excel_reader` - Funktionen `xlsx_chunk_reader.read_xlsx_in_chunks` kan ikke læse hele excel filen, den fejler efter chunk nr. 6 med en exception fra pandas.

- `test_excel_reader` - Excel filen åbnes på ny, hver gang der skal læses en del af den. Åbningen tager ca. 2 sekunder,
så for 21K rækker tager det 42 sekunder at læse filen.

### Downloader
- `test_corrupted_download` - Korupte filer slettes ikke korrekt, der prøves en `unlink` på en åben fil.
- `test_needs_user_agent` - Mange hjemmesider kræver en user-agent i headeren.
- `test_redirect_with_cookie` - Nogle links peger på en omdirigerings side, der sætter en cookie. Hvis den ikke findes når destinationen nåes, afvises brugeren.
- `test_zerosize_download` - Filer med størrelse 0 skal ikke gemmes.
- `test_ssl_cert_error` - En del links i Excel filerne har ugyldige SSL certifikater, som resulterer i afvisning af downloads. Deaktivering af SSL løser dette.
- `test_unsupported_encryption` - PyPDF2 kræver `pycryptodome` for at kunne åbne filer med AES kryptering. Hvis det ikke er installeret, fejler åbningen og en gyldig fil slettes.
- `test_url_no_scheme` - En del links mangler `http://` eller `https://` i Excel filerne. Disse links ignorers, selvom de er gyldige.

### Status file
Blev brugt til at blive bekendt med pytest, kan ignoreres.


## Kode kvalitet
### Navngivningskonventioner
- God ensartet navgivning af funktioner og variabler.
- Status- og ui relateret funktioner i `downloader.py` burde ligge i deres egne filer.

### Let at forstå/vedligeholde?
Veldokumenteret kode, og logikken er let at følge.

### Fejlhåndtering


## Testdækning og evt. forbedringer


## Kommentarer vedr. fejl/ineffektivitet
- status på enkelte filer, ikke hele mængden af downloads.
- Brug af threads til downloads, 60 sekunders timeout.