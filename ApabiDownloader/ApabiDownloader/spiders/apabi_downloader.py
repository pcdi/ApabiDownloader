import os.path

import scrapy
import logging
import urllib.parse


def authentication_failed(response):
    # If this text is present, authentication has failed.
    if auth_failed := response.xpath("//p/text()").re("您尚未登陆。"):
        return auth_failed


def get_image(response, page):
    logging.info(f"Got page {page}.")
    yield {"page": str(page), "image": response.body}


class ApabiDownloaderSpider(scrapy.Spider):
    name = "apabi_downloader"
    allowed_domains = ["apabi.lib.pku.edu.cn"]
    start_urls = ["http://apabi.lib.pku.edu.cn/Usp/pku/pub.mvc/?pid=login&cult=CN"]
    var_dict = None
    page_total = None

    def parse(self, response):
        return scrapy.FormRequest.from_response(
            response=response,
            formdata={"LoginType": "IPAutoLogin", "cult": "CN"},
            callback=self.after_login,
        )

    def after_login(self, response):
        if authentication_failed(response):
            self.logger.error("Login failed")
            return
        self.logger.info("Login successful.")
        return scrapy.Request(
            url="http://apabi.lib.pku.edu.cn/Usp/pku/?pid=book.detail&metaid=m.20151015-ZCKM-902-0064&cult=CN",
            callback=self.after_book_infopage,
        )

    def after_book_infopage(self, response):
        self.logger.info("Got book info page.")
        if online_read_page := response.xpath(
            '//a[contains(@type, "onlineread")]'
        ).attrib["href"]:
            online_read_page = response.urljoin(online_read_page)
            return scrapy.Request(online_read_page, callback=self.on_online_read_page)

    def on_online_read_page(self, response):
        self.logger.info("Got online read page.")
        self.create_var_dict(response)
        yield self.get_page_total(response)

    def get_img_url(self, response):
        self.set_page_total(response)
        downloaded_items = []
        for page in range(self.page_total):
            if os.path.isfile(f"output/{str(page + 1)}.png"):
                downloaded_items.append(page + 1)
        # From reader.js:657; function getUrl(page)
        # See also reader.js:2499; window.onload for value initialization
        img_url = response.urljoin("command/imagepage.ashx")
        self.page_total = 1
        for current_page in range(1, self.page_total + 1):
            if current_page in downloaded_items:
                self.logger.info(
                    f"Already downloaded page {str(current_page)}, skipping."
                )
                continue
            self.logger.info(f"Getting page {current_page}.")
            yield scrapy.FormRequest(
                url=img_url,
                method="GET",
                formdata={
                    "objID": self.var_dict["txtFileID"],
                    "metaId": self.var_dict["txtMetaId"],
                    "OrgId": self.var_dict["txtOrgIdentifier"],
                    "scale": "1",
                    "width": "9999",
                    "height": "9999",
                    "pageid": str(current_page),
                    "ServiceType": "Imagepage",
                    "SessionId": self.var_dict["txtSessionId"],
                    "UserName": self.var_dict["txtuserName"],
                    "cult": self.var_dict["txtCultureName"],
                    "rights": self.var_dict["rights"],
                    "time": self.var_dict["time"],
                    "sign": self.var_dict["sign"],
                },
                callback=get_image,
                cb_kwargs={"page": current_page},
            )

    def create_var_dict(self, response):
        var_dict = {}
        for var in response.xpath("//input"):
            if "value" in var.attrib:
                var_dict.update({var.attrib["id"]: var.attrib["value"]})
        # Some values are hidden as a string in one entry, need to dissect that
        var_dict.update(urllib.parse.parse_qsl(var_dict["urlrights"]))
        self.var_dict = var_dict

    def get_page_total(self, response):
        self.logger.info("Getting page total.")
        # See reader.js:1692
        return scrapy.FormRequest(
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
        )

    def set_page_total(self, response):
        self.page_total = int(response.xpath("//Content").attrib["TotalNum"])
        self.logger.info(f"Book has {self.page_total} pages.")
