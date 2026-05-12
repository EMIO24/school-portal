def render_template(template_body: str, context: dict) -> str:
    try:
        return template_body.format_map(context)
    except (KeyError, ValueError):
        return template_body
