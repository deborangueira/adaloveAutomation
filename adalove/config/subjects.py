SUBJECTS: list[str] = [
    "Matemática",
    "UX",
    "Programação",
    "Negócios",
    "Liderança",
    "Orientação",
    "Não presente no módulo",
]

# Inteli's curriculum "eixo" codes (Activity.axis_caption), used to infer a
# teacher's subject automatically instead of asking for every one by hand.
# "Orientação" has no axis of its own — it comes from the section's advisor,
# not from any activity — so it's deliberately absent here.
AXIS_TO_SUBJECT: dict[str, str] = {
    "COM": "Programação",
    "MTF": "Matemática",
    "NEG": "Negócios",
    "UEX": "UX",
    "LID": "Liderança",
}
