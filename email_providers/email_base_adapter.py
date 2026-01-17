from abc import ABC, abstractmethod


class EmailAdapter(ABC):
    @abstractmethod
    def send_html_email(self, from_: str, to: str, subject: str, html: str):
        raise NotImplementedError
