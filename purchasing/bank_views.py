from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from purchasing.models import Bank


@login_required
def bank_list(request):
    """List all banks"""
    banks = Bank.objects.all().order_by('nama_bank')
    return render(request, 'purchasing/bank_list.html', {'banks': banks})


@login_required
@require_http_methods(["GET", "POST"])
def bank_create(request):
    """Create new bank"""
    if request.method == 'POST':
        try:
            nama_bank = request.POST.get('nama_bank', '').strip()
            nomor_rekening = request.POST.get('nomor_rekening', '').strip()
            atas_nama = request.POST.get('atas_nama', '').strip()
            notes = request.POST.get('notes', '').strip()
            
            if not nama_bank or not nomor_rekening:
                messages.error(request, 'Nama Bank dan Nomor Rekening wajib diisi!')
                return render(request, 'purchasing/bank_form.html', {
                    'form_data': request.POST,
                    'is_edit': False
                })
            
            # Check if bank with same account number exists
            if Bank.objects.filter(nomor_rekening=nomor_rekening).exists():
                messages.error(request, f'Nomor rekening {nomor_rekening} sudah terdaftar!')
                return render(request, 'purchasing/bank_form.html', {
                    'form_data': request.POST,
                    'is_edit': False
                })
            
            Bank.objects.create(
                nama_bank=nama_bank,
                nomor_rekening=nomor_rekening,
                atas_nama=atas_nama,
                notes=notes,
                is_active=True
            )
            
            messages.success(request, f'Bank {nama_bank} berhasil ditambahkan!')
            return redirect('purchasing:bank_list')
            
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
            return render(request, 'purchasing/bank_form.html', {
                'form_data': request.POST,
                'is_edit': False
            })
    
    # GET request
    return render(request, 'purchasing/bank_form.html', {'is_edit': False})


@login_required
@require_http_methods(["GET", "POST"])
def bank_edit(request, bank_id):
    """Edit bank"""
    bank = get_object_or_404(Bank, id=bank_id)
    
    if request.method == 'POST':
        try:
            nama_bank = request.POST.get('nama_bank', '').strip()
            nomor_rekening = request.POST.get('nomor_rekening', '').strip()
            atas_nama = request.POST.get('atas_nama', '').strip()
            notes = request.POST.get('notes', '').strip()
            is_active = request.POST.get('is_active') == 'on'
            
            if not nama_bank or not nomor_rekening:
                messages.error(request, 'Nama Bank dan Nomor Rekening wajib diisi!')
                return render(request, 'purchasing/bank_form.html', {
                    'bank': bank,
                    'form_data': request.POST,
                    'is_edit': True
                })
            
            # Check if bank with same account number exists (excluding current bank)
            if Bank.objects.filter(nomor_rekening=nomor_rekening).exclude(id=bank_id).exists():
                messages.error(request, f'Nomor rekening {nomor_rekening} sudah terdaftar!')
                return render(request, 'purchasing/bank_form.html', {
                    'bank': bank,
                    'form_data': request.POST,
                    'is_edit': True
                })
            
            bank.nama_bank = nama_bank
            bank.nomor_rekening = nomor_rekening
            bank.atas_nama = atas_nama
            bank.notes = notes
            bank.is_active = is_active
            bank.save()
            
            messages.success(request, f'Bank {nama_bank} berhasil diupdate!')
            return redirect('purchasing:bank_list')
            
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
            return render(request, 'purchasing/bank_form.html', {
                'bank': bank,
                'form_data': request.POST,
                'is_edit': True
            })
    
    # GET request
    return render(request, 'purchasing/bank_form.html', {'bank': bank, 'is_edit': True})


@login_required
@require_POST
def bank_delete(request, bank_id):
    """Delete bank"""
    bank = get_object_or_404(Bank, id=bank_id)
    
    try:
        nama_bank = bank.nama_bank
        bank.delete()
        messages.success(request, f'Bank {nama_bank} berhasil dihapus!')
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
    
    return redirect('purchasing:bank_list')


@login_required
def bank_api(request):
    """API endpoint for banks"""
    banks = Bank.objects.all().order_by('nama_bank')
    
    data = []
    for bank in banks:
        data.append({
            'id': bank.id,
            'nama_bank': bank.nama_bank,
            'nomor_rekening': bank.nomor_rekening,
            'atas_nama': bank.atas_nama or '-',
            'is_active': bank.is_active,
            'notes': bank.notes or '-',
            'created_at': bank.created_at.strftime('%d %b %Y'),
        })
    
    return JsonResponse({'data': data})



