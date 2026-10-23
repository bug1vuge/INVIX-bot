"""All user-facing strings live here so copy changes don't touch handlers."""

CREATE_PRODUCT_BUTTON = "Создать товар"
CANCEL_BUTTON = "Отмена"
OPEN_CATALOG_BUTTON = "Открыть каталог"
MENU_BUTTON = "Каталог"

GREETING = "У меня есть товар"
GREETING_ADMIN_HINT = (
    "Чтобы добавить товар, нажмите «{button}» или сразу отправьте фото с названием в подписи."
)

ASK_PRODUCT = (
    "Отправьте <b>одним сообщением</b> фотографию товара, "
    "а в подписи к ней укажите название.\n\n"
    "Чтобы передумать, нажмите «{cancel}»."
)
CANCELLED = "Добавление товара отменено."
NOTHING_TO_CANCEL = "Сейчас нечего отменять."

NEED_PHOTO = "Нужна фотография товара с названием в подписи."
NEED_CAPTION = "Добавьте название товара в подпись к фото и отправьте ещё раз."
NAME_TOO_LONG = "Название слишком длинное: максимум {limit} символов."
ONLY_ONE_PHOTO = "Пришлите одну фотографию, альбомы не поддерживаются."
UNSUPPORTED_FILE = "Поддерживаются только изображения JPEG, PNG и WebP."
PHOTO_TOO_LARGE = "Файл слишком большой: максимум {limit} МБ."

PRODUCT_CREATED = "Товар «{name}» добавлен в каталог."
PRODUCT_REJECTED = "Не удалось добавить товар: {reason}"
PRODUCT_FAILED = "Сервис каталога сейчас недоступен. Попробуйте ещё раз через минуту."

API_REASONS = {
    "invalid_image": "файл не похож на изображение",
    "image_too_large": "изображение слишком большое",
    "invalid_name": "некорректное название",
}
