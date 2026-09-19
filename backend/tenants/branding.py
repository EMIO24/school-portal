import re
from rest_framework import serializers

LAYOUTS = ['scholar', 'campus', 'studio', 'executive', 'heritage']
FONTS = ["'Segoe UI', sans-serif", "Georgia, serif", "Arial, sans-serif", "Roboto, sans-serif"]

def validate_theme(value):
    if not isinstance(value, dict):
        raise serializers.ValidationError('Theme must be an object.')
    allowed = {'primary_color', 'secondary_color', 'accent_color', 'font_family', 'layout'}
    if set(value) - allowed:
        raise serializers.ValidationError('Only layout, primary_color, secondary_color, accent_color and font_family are supported.')
    for key in ('primary_color', 'secondary_color', 'accent_color'):
        if key in value and (not isinstance(value[key], str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', value[key])):
            raise serializers.ValidationError({key: 'Use a six-digit hex colour, such as #173B56.'})
    if 'layout' in value and value['layout'] not in LAYOUTS:
        raise serializers.ValidationError({'layout': 'Choose one of the five portal layouts.'})
    if 'font_family' in value and value['font_family'] not in FONTS:
        raise serializers.ValidationError({'font_family': 'Choose a supported font.'})
    return value
