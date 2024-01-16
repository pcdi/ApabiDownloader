import scrapy


def authentication_failed(response):
    # If this text is present, authentication has failed.
    if auth_failed := response.xpath("//p/text()").re("您尚未登陆。"):
        return auth_failed


class ApabiDownloaderSpider(scrapy.Spider):
    name = "apabi_downloader"
    allowed_domains = ["apabi.lib.pku.edu.cn"]
    start_urls = ["http://apabi.lib.pku.edu.cn/Usp/pku/pub.mvc/?pid=login&cult=CN"]

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
