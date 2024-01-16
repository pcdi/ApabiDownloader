import scrapy
import logging
import urllib.parse


def authentication_failed(response):
    # If this text is present, authentication has failed.
    if auth_failed := response.xpath("//p/text()").re("您尚未登陆。"):
        return auth_failed


class ApabiDownloaderSpider(scrapy.Spider):
    name = "apabi_downloader"
    allowed_domains = ["apabi.lib.pku.edu.cn"]
    start_urls = ["http://apabi.lib.pku.edu.cn/Usp/pku/pub.mvc/?pid=login&cult=CN"]
    page_total = 0

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
        logging.info("Login successful.")
        return scrapy.Request(
            url="http://apabi.lib.pku.edu.cn/Usp/pku/?pid=book.detail&metaid=m.20151015-ZCKM-902-0064&cult=CN",
            callback=self.after_book_infopage,
        )

    def after_book_infopage(self, response):
        logging.info("Got book info page.")
        if online_read_page := response.xpath(
            '//a[contains(@type, "onlineread")]'
        ).attrib["href"]:
            online_read_page = response.urljoin(online_read_page)
            return scrapy.Request(online_read_page, callback=self.on_online_read_page)

    def on_online_read_page(self, response):
        logging.info("Got online read page.")
        var_dict = {}

        for var in response.xpath("//input"):
            if "value" in var.attrib:
                var_dict.update({var.attrib["id"]: var.attrib["value"]})
        # Some values are hidden as a string in one entry, need to dissect that
        var_dict.update(urllib.parse.parse_qsl(var_dict["urlrights"]))

        # From reader.js:657; function getUrl(page)
        # See also reader.js:2499; window.onload for value initialization
        img_url = response.urljoin("command/imagepage.ashx")
        return scrapy.FormRequest(
            url=img_url,
            method="GET",
            formdata={
                "objID": var_dict["txtFileID"],
                "metaId": var_dict["txtMetaId"],
                "OrgId": var_dict["txtOrgIdentifier"],
                "scale": "1",
                "width": "9999",
                "height": "9999",
                "pageid": "1",
                "ServiceType": "Imagepage",
                "SessionId": var_dict["txtSessionId"],
                "UserName": var_dict["txtuserName"],
                "cult": var_dict["txtCultureName"],
                "rights": var_dict["rights"],
                "time": var_dict["time"],
                "sign": var_dict["sign"],
            },
            callback=self.get_image,
        )

    def get_image(self, response):
        with open("1.png", "wb") as outfile:
            outfile.write(response.body)
