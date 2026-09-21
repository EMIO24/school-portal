import re
from rest_framework import serializers

LAYOUTS = ['scholar', 'campus', 'studio', 'executive', 'heritage']
RESULT_LAYOUTS = ['classic', 'modern', 'compact']
RESULT_SECTION_OPTIONS = ['summary', 'scores', 'attendance', 'remarks', 'affective', 'psychomotor']
FONTS = ["'Segoe UI', sans-serif", "Georgia, serif", "Arial, sans-serif", "Roboto, sans-serif"]


def validate_theme(value):
    if not isinstance(value, dict):
        raise serializers.ValidationError('Theme must be an object.')
    allowed = {
        'primary_color', 'secondary_color', 'accent_color', 'font_family', 'layout',
        'result_layout', 'result_sections'
    }
    if set(value) - allowed:
        raise serializers.ValidationError(
            'Only layout, result_layout, result_sections, primary_color, secondary_color, '
            'accent_color and font_family are supported.'
        )
    for key in ('primary_color', 'secondary_color', 'accent_color'):
        if key in value and (not isinstance(value[key], str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', value[key])):
            raise serializers.ValidationError({key: 'Use a six-digit hex colour, such as #173B56.'})
    if 'layout' in value and value['layout'] not in LAYOUTS:
        raise serializers.ValidationError({'layout': 'Choose one of the five portal layouts.'})
    if 'result_layout' in value and value['result_layout'] not in RESULT_LAYOUTS:
        raise serializers.ValidationError({'result_layout': 'Choose one of the three result layouts: classic, modern or compact.'})
    if 'result_sections' in value:
        sections = value['result_sections']
        if not isinstance(sections, list):
            raise serializers.ValidationError({'result_sections': 'Choose a list of supported result sections.'})
        invalid = [section for section in sections if section not in RESULT_SECTION_OPTIONS]
        if invalid:
            raise serializers.ValidationError({'result_sections': f'Unsupported result sections: {invalid}'})
        if len(sections) != len(set(sections)):
            raise serializers.ValidationError({'result_sections': 'Result sections must not repeat.'})
    if 'font_family' in value and value['font_family'] not in FONTS:
        raise serializers.ValidationError({'font_family': 'Choose a supported font.'})
    return value
