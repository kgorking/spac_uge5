import os
from pdf_downloader.downloader import load_or_create_status_file, update_status, save_status_file

def test_status_file():
    test_file_name = "test_save_file.xlsx"
    df = None

    if os.path.exists(test_file_name):
        os.unlink(test_file_name)

    df = load_or_create_status_file(test_file_name)

    assert(df.size == 0)
    assert(df.columns.size == 3)
    assert(df.columns.isin(["BRnum", "Status", "Info"]).all())

    df = update_status(df, "brnum:test", "status:testing", "info:testing")

    save_status_file(df, test_file_name)
    assert(os.path.exists(test_file_name))

    df = load_or_create_status_file(test_file_name)
    assert df.size > 0
    os.unlink(test_file_name)

