# Apabi Downloader

## Features

This program downloads single page images from Apabi Digital Library (阿帕比电子图书).

## How To Use

You will need to have [Git](https://git-scm.com/) and Python 3 with pip/[pipenv](https://pipenv.pypa.io/en/latest/) installed on your computer.
Then [install the dependencies](https://pipenv.pypa.io/en/latest/workflows.html) thusly:

1. Clone this repository:
    ```{shell}
    git clone https://github.com/pcdi/ApabiDownloader.git
    ```
2. Go into the repository:
    ```{shell}
    cd ApabiDownloader
    ```
3. Install dependencies:
    ```{shell}
    pipenv sync
    ```
4. Go into the crawler's directory:
    ```{shell}
    cd ApabiDownloader
    ```
   You should now be at `ApabiDownloader/ApabiDownloader`, the folder that contains `scrapy.cfg`.
5. Make sure you are able to log into Apabi via your IP! Otherwise, the program will not be able to download anything. For example: Either be physically at the institution that gives you access to Apabi or be connected via VPN.
6. Run the program. The information about the book you want to download should be supplied as an argument. Make sure you supply a URL that contains `book.detail`. In the following command, replace the URL with your own URL:
    ```{shell}
    pipenv run scrapy crawl apabi_downloader -L INFO -a book_detail_url="http://apabi.lib.pku.edu.cn/Usp/pku/?pid=book.detail&metaid=m.20201211-ZGRM-KXSJ-0307"
    ```
7. To stop the crawler, either wait for it to finish running or exit with <key>Ctrl-C</key>.
8. If the crawler has not downloaded all images for the book, you can restart the crawler running the same command again. It will only download pages that have not been previously downloaded.