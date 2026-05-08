{{ soul }}

{% if user_prefs %}
## User Preferences
{{ user_prefs }}
{% endif %}

{% if identity %}
## Workspace Identity
{{ identity }}
{% endif %}

{% if long_term_memory %}
## Long-term Memory
{{ long_term_memory }}
{% endif %}

{% if skills_summary %}
## Available Skills
{{ skills_summary }}
{% endif %}

{% if extra %}
## Additional Context
{{ extra }}
{% endif %}
