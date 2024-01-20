import urllib.parse
from datetime import datetime
from pathlib import Path

import scrapy


def authentication_failed(response):
    # If this text is present, authentication has failed.
    if auth_failed := response.xpath("//p/text()").re("您尚未登陆。"):
        return auth_failed


class ApabiDownloaderSpider(scrapy.Spider):
    name = "apabi_downloader"
    output_dir_base = "output/"

    def __init__(self, book_detail_url=None, *args, **kwargs):
        super(ApabiDownloaderSpider, self).__init__(*args, **kwargs)
        self.allowed_domains = [urllib.parse.urlparse(book_detail_url).netloc]
        self.var_dict = None
        self.page_total = None
        self.downloaded_items = None
        self.book_detail_url = book_detail_url
        self.img_url = None
        self.output_folder_name = None
        self.output_dir = None
        self.make_output_dir()

    def make_output_dir(self):
        self.logger.info("Making output directory.")
        try:
            self.output_folder_name = urllib.parse.parse_qs(self.book_detail_url)["metaid"][0].lstrip("m.")
            self.output_dir = self.output_dir_base + self.output_folder_name
            Path(self.output_dir_base).mkdir(exist_ok=True)
            Path(self.output_dir).mkdir(exist_ok=True)
        except Exception as e:
            self.logger.exception(e)
            raise

    def start_requests(self):
        start_url = urllib.parse.urljoin(self.book_detail_url, "pub.mvc/?pid=login&cult=CN")
        yield from [scrapy.Request(url=start_url, callback=self.parse)]

    def parse(self, response):
        yield scrapy.FormRequest.from_response(
            response=response,
            formdata={"LoginType": "IPAutoLogin", "cult": "CN"},
            callback=self.after_login,
        )

    def after_login(self, response):
        if authentication_failed(response):
            self.logger.error("Login failed.")
            return
        self.logger.info("Login successful.")
        yield scrapy.Request(
            url=self.book_detail_url,
            callback=self.after_book_infopage,
            dont_filter=True
        )

    def after_book_infopage(self, response):
        self.logger.info("Got book info page.")
        if online_read_page := response.xpath(
                '//a[contains(@type, "onlineread")]'
        ).attrib["href"]:
            online_read_page = response.urljoin(online_read_page)
            yield scrapy.Request(online_read_page, callback=self.on_online_read_page, dont_filter=True)

    def create_var_dict(self, response):
        var_dict = {}
        for var in response.xpath("//input"):
            if "value" in var.attrib:
                var_dict.update({var.attrib["id"]: var.attrib["value"]})
        # Some values are hidden as a string in one entry, need to dissect that
        var_dict.update(urllib.parse.parse_qsl(var_dict["urlrights"]))
        self.var_dict = var_dict
        self.logger.info(
            f'Downloading {self.var_dict["bookName"]} by {self.var_dict["creator"]}. '
            f'Access is provided by {self.var_dict["txtOrgIdentifier"]}.')

    def on_online_read_page(self, response):
        self.logger.info("Got online read page.")
        self.create_var_dict(response)
        if self.page_total is None:
            yield from self.get_page_total(response)
        else:
            yield from self.get_img_url(response)

    def get_page_total(self, response):
        self.logger.info("Getting page total.")
        # See reader.js:1692
        yield scrapy.FormRequest(
            url=response.urljoin("Command/Getcontent.ashx"),
            method="GET",
            formdata={
                "OrgIdentifier": self.var_dict["txtOrgIdentifier"],
                "objID": self.var_dict["txtFileID"],
                "parentIndex": "0",
                "ServiceType": "getcontent",
                "metaId": self.var_dict["txtMetaId"],
                "OrgId": self.var_dict["txtOrgIdentifier"],
                "SessionId": self.var_dict["txtSessionId"],
                "cult": self.var_dict["txtCultureName"],
                "UserName": self.var_dict["txtuserName"],
            },
            callback=self.get_img_url,
            dont_filter=True
        )

    def set_page_total(self, response):
        self.page_total = int(response.xpath("//Content").attrib["TotalNum"])
        self.logger.info(f"Book has {self.page_total} pages.")

    def get_img_url(self, response):
        if self.page_total is None:
            self.set_page_total(response)
        self.downloaded_items = []
        for page in range(self.page_total):
            if Path(f"{self.output_dir}/{str(page + 1)}.png").is_file():
                self.downloaded_items.append(page + 1)
        # From reader.js:657; function getUrl(page)
        # See also reader.js:2499; window.onload for value initialization
        self.img_url = response.urljoin("command/imagepage.ashx")
        page = self.get_next_page_to_download(start_page=1)
        yield from self.request_img(response, page)

    def get_next_page_to_download(self, start_page):
        page = start_page
        while page in self.downloaded_items:
            page += 1
        return page

    def is_timed_out(self):
        timeout_time = datetime.strptime(self.var_dict["time"], "%Y-%m-%d %H:%M:%S")
        time_left = timeout_time - datetime.utcnow()
        if time_left.seconds > 30:
            return False
        else:
            return True

    def get_new_timeslot(self, response):
        self.logger.info("Timeout, getting new timeslot.")
        yield from self.after_login(response)

    def request_img(self, response, page):
        if self.is_timed_out():
            yield from self.after_login(response)
        else:
            self.logger.info(f"Getting page {page}.")
            yield scrapy.FormRequest(
                url=self.img_url,
                method="GET",
                formdata={
                    "objID": self.var_dict["txtFileID"],
                    "metaId": self.var_dict["txtMetaId"],
                    "OrgId": self.var_dict["txtOrgIdentifier"],
                    "scale": "1",
                    "width": "9999",
                    "height": "9999",
                    "pageid": str(page),
                    "ServiceType": "Imagepage",
                    "SessionId": self.var_dict["txtSessionId"],
                    "UserName": self.var_dict["txtuserName"],
                    "cult": self.var_dict["txtCultureName"],
                    "rights": self.var_dict["rights"],
                    "time": self.var_dict["time"],
                    "sign": self.var_dict["sign"],
                },
                callback=self.get_image,
                cb_kwargs={"page": page},
                meta={"handle_httpstatus_list": [403]}
            )

    def get_image(self, response, page):
        if response.status == 403 or self.is_timed_out() is True:
            yield from self.get_new_timeslot(response)
        else:
            self.logger.info(f"Got page {page}.")
            yield {"page": str(page), "image": response.body}
            next_page = self.get_next_page_to_download(page + 1)
            if next_page <= self.page_total:
                yield from self.request_img(response, next_page)
