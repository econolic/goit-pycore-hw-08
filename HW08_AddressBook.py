import pickle
import logging
from datetime import datetime, date, timedelta
from collections import UserDict
from typing import List, Optional
from colorama import Fore, Style, init

# -------------------------------------------------------------------
# 1. Налаштування Colorama і логування
# -------------------------------------------------------------------
init(autoreset=True)
logging.basicConfig(
    filename="addressbook.log",
    level=logging.ERROR,
    format="%(asctime)s %(levelname)s: %(message)s"
)

PICKLE_FILE = "addressbook.pkl"


# -------------------------------------------------------------------
# 2. Декоратор для обробки помилок @input_error
# -------------------------------------------------------------------
def input_error(func):
    """
    Декоратор для обробки помилок при виконанні команд.
    Логує помилки і виводить повідомлення користувачеві з підсвіткою.
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyError as e:
            logging.error(f"KeyError in {func.__name__}: {e}")
            print(Fore.RED + "Контакт з таким іменем не знайдено." + Style.RESET_ALL)
        except ValueError as e:
            logging.error(f"ValueError in {func.__name__}: {e}")
            print(Fore.RED + f"{e}" + Style.RESET_ALL)
        except IndexError:
            logging.error(f"IndexError in {func.__name__}: Not enough arguments.")
            print(Fore.RED + "Неправильний формат команди або недостатньо аргументів." + Style.RESET_ALL)
        except Exception as e:
            logging.error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)
            print(Fore.RED + f"Сталася несподівана помилка: {e}" + Style.RESET_ALL)
    return wrapper


# -------------------------------------------------------------------
# 3. Класи для адресної книги
# -------------------------------------------------------------------
class Field:
    """Базовий клас для усіх полів (Name, Phone, Birthday)."""
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)


class Name(Field):
    """Ім'я контакту (обов'язкове поле)."""
    pass


class Phone(Field):
    """
    Зберігає номер телефону і перевіряє, що він складається рівно з 10 цифр.
    """
    def __init__(self, value: str):
        if not isinstance(value, str):
            raise ValueError("Телефон має бути рядком, що містить 10 цифр.")
        if not (value.isdigit() and len(value) == 10):
            raise ValueError("Телефонний номер повинен складатися рівно з 10 цифр.")
        super().__init__(value)


class Birthday(Field):
    """
    Зберігає день народження як datetime.date.
    Рядок повинен бути у форматі DD.MM.YYYY.
    """
    def __init__(self, value: str):
        try:
            parsed = datetime.strptime(value, "%d.%m.%Y").date()
        except ValueError:
            raise ValueError("Дата повинна бути у форматі DD.MM.YYYY і бути коректною датою.")
        super().__init__(parsed)

    def __str__(self):
        return self.value.strftime("%d.%m.%Y")


class Record:
    """
    Запис (контакт) містить:
    - Name (обов'язкове)
    - Список Phone
    - Опціонально Birthday
    """
    def __init__(self, name: str):
        self.name = Name(name)
        self.phones: List[Phone] = []
        self.birthday: Optional[Birthday] = None

    def add_phone(self, phone_str: str):
        """Додає номер телефону, якщо він ще не доданий."""
        phone_obj = Phone(phone_str)
        if not any(p.value == phone_obj.value for p in self.phones):
            self.phones.append(phone_obj)

    def remove_phone(self, phone_str: str):
        """Видаляє номер телефону, якщо він є."""
        for ph in self.phones:
            if ph.value == phone_str:
                self.phones.remove(ph)
                break

    def edit_phone(self, old_phone: str, new_phone: str):
        """Замінює старий номер на новий, якщо старий знайдено."""
        for idx, ph in enumerate(self.phones):
            if ph.value == old_phone:
                new_phone_obj = Phone(new_phone)
                self.phones[idx] = new_phone_obj
                return True
        return False

    def add_birthday(self, bday_str: str):
        """Встановлює або оновлює день народження."""
        self.birthday = Birthday(bday_str)

    def show_birthday(self) -> str:
        """Повертає день народження або повідомлення, що не задано."""
        if self.birthday:
            return str(self.birthday)
        return "День народження не задано"

    def __str__(self):
        phones_str = ", ".join(ph.value for ph in self.phones)
        if self.birthday:
            return f"{self.name.value}: {phones_str}, birthday: {self.birthday}"
        return f"{self.name.value}: {phones_str}"


class AddressBook(UserDict):
    """
    Адресна книга як контейнер записів (Record), де ключ — ім'я контакту.
    """
    def add_record(self, record: Record):
        self.data[record.name.value] = record

    def find(self, name: str) -> Record:
        rec = self.data.get(name)
        if rec is None:
            raise KeyError(f"{name} not found in AddressBook.")
        return rec

    def delete(self, name: str) -> bool:
        if name in self.data:
            del self.data[name]
            return True
        return False

    def get_upcoming_birthdays(self) -> List[dict]:
        """
        Повертає список записів, у яких день народження протягом наступних 7 днів.
        Якщо ДН припадає на вихідні, переносить привітання на наступний понеділок.
        """
        today = date.today()
        upcoming = []
        for record in self.data.values():
            if record.birthday is None:
                continue
            bday: date = record.birthday.value
            birthday_this_year = bday.replace(year=today.year)
            if birthday_this_year < today:
                birthday_this_year = birthday_this_year.replace(year=today.year + 1)
            days_ahead = (birthday_this_year - today).days
            if 0 <= days_ahead <= 6:
                if birthday_this_year.weekday() == 5:  # субота
                    congratulation_date = birthday_this_year + timedelta(days=2)
                elif birthday_this_year.weekday() == 6:  # неділя
                    congratulation_date = birthday_this_year + timedelta(days=1)
                else:
                    congratulation_date = birthday_this_year
                upcoming.append({
                    "name": record.name.value,
                    "congratulation_date": congratulation_date.strftime("%Y.%m.%d")
                })
        return upcoming


# -------------------------------------------------------------------
# 4. Функції для збереження/завантаження даних за допомогою pickle
# -------------------------------------------------------------------
def save_data(book: AddressBook, filename: str = PICKLE_FILE):
    """Зберігає AddressBook у файл за допомогою pickle."""
    with open(filename, "wb") as f:
        pickle.dump(book, f)


def load_data(filename: str = PICKLE_FILE) -> AddressBook:
    """Завантажує AddressBook з файлу. Якщо файл не знайдено, повертає порожню книгу."""
    try:
        with open(filename, "rb") as f:
            return pickle.load(f)
    except FileNotFoundError:
        print(Fore.YELLOW + f"Файл {filename} не знайдено. Створено нову адресну книгу." + Style.RESET_ALL)
        return AddressBook()


# -------------------------------------------------------------------
# 5. Функції-обробники команд
# -------------------------------------------------------------------
@input_error
def add_contact(args: list, book: AddressBook) -> str:
    """add [name] [phone] – додає новий контакт або номер до існуючого."""
    name, phone = args[0], args[1]
    try:
        record = book.find(name)
        record.add_phone(phone)
        return f"Для контакту {name} додано номер {phone}."
    except KeyError:
        record = Record(name)
        record.add_phone(phone)
        book.add_record(record)
        return f"Створено новий контакт: {name} з номером {phone}."


@input_error
def change_phone(args: list, book: AddressBook) -> str:
    """change [name] [old_phone] [new_phone] – змінює номер телефону."""
    name, old_phone, new_phone = args[0], args[1], args[2]
    record = book.find(name)
    changed = record.edit_phone(old_phone, new_phone)
    if changed:
        return f"У {name} замінено номер {old_phone} на {new_phone}."
    return f"У {name} не знайдено номер {old_phone}."


@input_error
def show_phones(args: list, book: AddressBook) -> str:
    """phone [name] – показує всі номери телефону для контакту."""
    name = args[0]
    record = book.find(name)
    if not record.phones:
        return f"У {name} немає телефонних номерів."
    phones_str = ", ".join(ph.value for ph in record.phones)
    return f"Контакт {name}, телефони: {phones_str}"


@input_error
def show_all(args: list, book: AddressBook) -> str:
    """all – показує всі контакти в адресній книзі."""
    if not book.data:
        return "Адресна книга порожня."
    lines = [str(record) for record in book.data.values()]
    return "\n".join(lines)


@input_error
def add_birthday(args: list, book: AddressBook) -> str:
    """add-birthday [name] [DD.MM.YYYY] – встановлює день народження для контакту."""
    name, bday_str = args[0], args[1]
    record = book.find(name)
    record.add_birthday(bday_str)
    return f"Для {name} встановлено день народження: {bday_str}"


@input_error
def show_birthday(args: list, book: AddressBook) -> str:
    """show-birthday [name] – показує день народження контакту."""
    name = args[0]
    record = book.find(name)
    bday_info = record.show_birthday()
    if bday_info == "День народження не задано":
        return f"У {name} день народження не вказано."
    return f"День народження {name}: {bday_info}"


@input_error
def show_upcoming_birthdays(args: list, book: AddressBook) -> str:
    """
    birthdays – показує, у кого день народження протягом наступних 7 днів,
    з переносом привітання на понеділок, якщо необхідно.
    """
    upcoming = book.get_upcoming_birthdays()
    if not upcoming:
        return "На наступному тижні немає іменинників."
    lines = ["Ось хто святкує День народження протягом наступних 7 днів:"]
    for person in upcoming:
        lines.append(f"{person['name']} => {person['congratulation_date']}")
    return "\n".join(lines)


@input_error
def greet(args: list, book: AddressBook) -> str:
    """hello – виводить привітальне повідомлення."""
    return "Привіт! Чим можу допомогти?"


# -------------------------------------------------------------------
# 6. Головна функція main() з циклом командного інтерфейсу
# -------------------------------------------------------------------
def main():
    """
    Головна точка входу.
    Завантажує (або створює) AddressBook з файлу pickle, запускає цикл вводу команд,
    а перед виходом зберігає дані.
    """
    choice = input("Load existing address book from pickle? (y/n): ").strip().lower()
    if choice.startswith("y"):
        address_book = load_data(PICKLE_FILE)
    else:
        address_book = AddressBook()
        print("Створено нову (порожню) адресну книгу.")

    COMMANDS = {
        "add": add_contact,
        "change": change_phone,
        "phone": show_phones,
        "all": show_all,
        "add-birthday": add_birthday,
        "show-birthday": show_birthday,
        "birthdays": show_upcoming_birthdays,
        "hello": greet
    }

    print("Вітаю! Це бот адресної книги. Наберіть 'help' для перегляду списку команд.")

    while True:
        user_input = input(">>> ").strip()
        if not user_input:
            continue
        parts = user_input.split()
        command = parts[0].lower()
        args = parts[1:]

        if command in ("exit", "close"):
            print("До побачення! Зберігаю книгу...")
            save_data(address_book, PICKLE_FILE)
            break
        elif command == "help":
            print(Fore.YELLOW + "Підтримувані команди:\n" + Style.RESET_ALL +
                  "  hello\n"
                  "  add [name] [phone]\n"
                  "  change [name] [old_phone] [new_phone]\n"
                  "  phone [name]\n"
                  "  all\n"
                  "  add-birthday [name] [DD.MM.YYYY]\n"
                  "  show-birthday [name]\n"
                  "  birthdays\n"
                  "  close або exit (для завершення)\n")
        elif command in COMMANDS:
            handler = COMMANDS[command]
            result = handler(args, address_book)
            if result is not None:
                print(result)
        else:
            print(Fore.CYAN + "Невідома команда. Спробуйте 'help' для перегляду доступних команд." + Style.RESET_ALL)


if __name__ == "__main__":
    main()
