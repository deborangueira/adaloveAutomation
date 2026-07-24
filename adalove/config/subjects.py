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

# Fixed categorical hues (validated for colorblind-safe adjacent contrast),
# one per subject, kept in this order everywhere a subject gets a color —
# never reassigned when the set of subjects present changes.
SUBJECT_COLORS: dict[str, str] = {
    "Matemática": "#2a78d6",
    "UX": "#eb6834",
    "Programação": "#1baf7a",
    "Negócios": "#eda100",
    "Liderança": "#e87ba4",
    "Orientação": "#008300",
}
