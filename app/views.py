from django.shortcuts import render
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def home(request):
    return render(request, 'home.html')


@csrf_exempt
def submit_contact_form(request):
    if request.method == 'POST':
        data = {
            "Name": request.POST.get('name'),
            "Email": request.POST.get('email'),
            "Phone": request.POST.get('phone'),
            "Education": request.POST.get('education'),
            "Experience": request.POST.get('experience'),
            "Place": request.POST.get('place'),
            "Reason": request.POST.get('reason'),
        }

        # Connect to Google Sheets
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('bthinkx-d17e6d002985.json', scope)
        client = gspread.authorize(creds)

        # Open sheet and append data
        sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1TbW3WBVmlhARWYdf6LN7_wpSq0ir1YYZ4oOQFV9-xsg/edit")
        worksheet = sheet.sheet1
        worksheet.append_row(list(data.values()))

        return redirect('/')  # Or success page