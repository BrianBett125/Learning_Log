from django import forms
from .models import Topic, Entry

class TopicForm(forms.ModelForm):
    class Meta:
        model = Topic
        fields = ['text']
        labels = {'text': ''}
        # The reference omits the visible label, which left the control with no
        # accessible name (axe: CRITICAL 'label'). An aria-label names it for
        # screen readers without adding anything visible.
        widgets = {'text': forms.TextInput(attrs={'aria-label': 'Topic text'})}

class EntryForm(forms.ModelForm):
    class Meta:
        model = Entry
        fields = ['text']
        labels = {'text': ''}
        widgets = {'text': forms.Textarea(attrs={'cols':80, 'aria-label': 'Entry text'})}

