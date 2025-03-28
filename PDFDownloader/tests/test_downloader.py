import os
from time import sleep
import requests
from pdf_downloader.downloader import attempt_download, download_single_pdf

# Download stuff into this pdf file
test_brnum = "BRtest"
test_filename = test_brnum + '.pdf'


# Returns the full url to the mock server for an endpoint
def mock_url(endpoint: str, ssl: bool = False) -> str:
    if ssl:
        return "https://127.0.0.1:12334/api/" + endpoint
    else:
        return "http://127.0.0.1:12333/api/" + endpoint


# Downloads an url
def mock_download_url(url: str) -> tuple[str, str]:
    return download_single_pdf(test_brnum, url, None, ".")


# Download from a mock server endpoint
def mock_download(endpoint: str, ssl: bool = False) -> tuple[str, str]:
    return mock_download_url(mock_url(endpoint, ssl))


# Removes the temp pdf file
def cleanup():
    if os.path.exists(test_filename):
        os.unlink(test_filename)


class TestDownloader:
    """
    TODO
    """

    @classmethod
    def setup_class(cls):
        # Make sure the mock HTTP/HTTPS servers are running
        http_is_live = mock_url("is_live")
        assert 200 == requests.get(http_is_live).status_code

        https_is_live = mock_url("ssl_is_live", True)
        assert 200 == requests.get(https_is_live, verify=False).status_code

    @classmethod
    def teardown_class(cls):
        # Do any needed cleanup
        cleanup()

    def test_simple_download(self):
        """
        Ensure that a simple download of an empty pdf works.
        """
        status, err = mock_download("get_empty")
        assert status == "Success"
        assert 4911 == os.path.getsize(test_filename)
        cleanup()

    def test_corrupted_download(self):
        """
        Ensure that a corrupted pdf is deleted after download.
        """
        status, err = mock_download("get_corrupted")
        assert status == "Failure"
        assert not os.path.exists(test_filename)
        cleanup()


    def test_zerosize_download(self):
        """
        Ensure that pdf with no content is deleted after download.
        """
        status, err = mock_download("get_zerosize")
        assert status == "Failure"
        assert not os.path.exists(test_filename)
        cleanup()

    def test_needs_user_agent(self):
        """
        Ensure that a valid user agent is set in the requests.
        Many servers deny request if it does not contain an approved user-agent,
        in order to prevent web-scraping etc.
        Adding a
          headers = {'User-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0'}
          request.get(..., headers=headers)
        to a request is usually enough to circumvent this.
        """
        # Happens on some urls, which fails with a 403 or 401 without a valid user-agent
        # * 401: https://www.dekabank.de/media/de/docs/investor-relations/geschaeftsberichte/2010/GB_2010-D_Nachhaltigkeitsbericht.pdf
        # * 403: https://vp224.alertir.com/afw/files/press/bonava/201703091534-1.pdf
        status, err = mock_download("needs_user_agent")
        assert status == "Success"
        cleanup()

    def test_redirect_with_cookie(self):
        """
        Ensure that cookies survive redirections.
        """
        status, err = mock_download("redir_with_cookie_set")
        assert status == "Success"
        cleanup()

    def test_ssl_cert_error(self):
        """
        Ensure that valid files can be downloaded
        from servers with invalid ssl certificates.
        There are quite a few of these in the dataset.
        """
        url = mock_url("ssl_get_empty", ssl=True)
        status, err = mock_download_url(url)
        assert status == "Success"
        cleanup()

    def test_unsupported_encryption(self):
        """
        Downloads a valid pdf, but it uses AES encryption, which is
        not supported by PyPDF without an installed library.
        This results in an error state, and the valid pdf is deleted
        """
        status, err = mock_download("get_aes_encrypted")
        assert status == "Success"
        cleanup()

    def test_url_no_scheme(self):
        """
        Ensure that an url without a prefixed 'http://' works
        """
        url = mock_url("get_empty")[7:]
        status, err = mock_download_url(url)
        assert status == "Success"
        cleanup()
