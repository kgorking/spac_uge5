import os
from utils.xlsx_chunk_reader import read_xlsx_in_chunks

def test_excel_reader():
    """
    The function tested reads rows in chunks, so make sure it
    reads all the rows in the excel file.
    Chunking sometimes goes wrong.
    """

    excel_file = os.path.dirname(os.path.abspath(__file__)) + '/../data/GRI_2017_2020 (1).xlsx'

    # The 'read_xlsx_in_chunks' functions opens the excel file on
    # every iteration, which takes about 2 seconds.
    # To just check the row-count, this test needs about 45 seconds to run.
    chunk_generator = read_xlsx_in_chunks(excel_file, chunk_size=1000)

    count = 0
    for chunk in chunk_generator:
        count += len(chunk["BRnum"])
    assert count == 21057
