from django.shortcuts import render

def index(request):
    """the homepage for learning_logs."""
    return render(request, 'learning_logs/index.html')


# Create your views here.
