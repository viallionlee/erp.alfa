delete folder venv
buat folder baru venv lg - python -m venv venv
install requirements.txt - pip install -r requirements.txt
activekan venv -  .\venv\Scripts\Activate.ps1 && echo $env:VIRTUAL_ENV

PS C:\ERP_ALFA> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
PS C:\ERP_ALFA> .\venv\Scripts\activate.bat
PS C:\ERP_ALFA> .\venv\Scripts\Activate.ps1
(venv) PS C:\ERP_ALFA> 