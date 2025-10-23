from django.db import models
from django.conf import settings
from django.utils import timezone


class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('received', 'Received'),
    ]
    
    nomor_po = models.CharField(max_length=100, unique=True, null=True, blank=True)
    supplier = models.ForeignKey('inventory.Supplier', on_delete=models.PROTECT, null=True, blank=True)
    tanggal_po = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    total_amount = models.IntegerField(default=0)  # Changed to IntegerField for easier formatting
    notes = models.TextField(blank=True, null=True)
    
    # Tracking fields
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='pos_created'
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='pos_received'
    )
    received_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-tanggal_po', '-id']
        verbose_name = 'Purchase Order'
        verbose_name_plural = 'Purchase Orders'
        permissions = [
            ('po_view', 'Can view Purchase Order'),
            ('po_marketing', 'Can create/edit Purchase Order (Marketing)'),
        ]
    
    def __str__(self):
        return f"{self.nomor_po or 'DRAFT'} - {self.supplier or 'No Supplier'}"
    
    def save(self, *args, **kwargs):
        # Auto-generate nomor_po hanya jika status bukan draft
        if self.pk and not self.nomor_po and self.status != 'draft':
            from django.utils import timezone
            from datetime import datetime
            # Generate nomor PO
            date_str = datetime.now().strftime('%Y%m%d')
            # Get next ID
            last_po = PurchaseOrder.objects.filter(
                nomor_po__startswith=f'PO-{date_str}'
            ).order_by('-nomor_po').first()
            
            if last_po and last_po.nomor_po:
                last_id = int(last_po.nomor_po.split('-')[-1])
                new_id = last_id + 1
            else:
                new_id = 1
            
            self.nomor_po = f"PO-{date_str}-{new_id:04d}"
        
        # Calculate total amount
        if self.pk:
            self.total_amount = sum(item.subtotal for item in self.items.all())
        super().save(*args, **kwargs)


class PurchaseOrderItem(models.Model):
    po = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT)
    quantity = models.IntegerField(default=0)
    harga_beli = models.IntegerField(default=0)  # Changed to IntegerField for easier formatting
    subtotal = models.IntegerField(default=0)  # Changed to IntegerField for easier formatting
    
    class Meta:
        ordering = ['product__nama_produk']
        unique_together = ('po', 'product')
    
    def __str__(self):
        return f"{self.po.nomor_po or 'DRAFT'} - {self.product.sku}"
    
    def save(self, *args, **kwargs):
        # Calculate subtotal
        self.subtotal = self.quantity * self.harga_beli
        super().save(*args, **kwargs)
        # Update PO total
        if self.po.pk:
            self.po.save()


class PurchaseOrderHistory(models.Model):
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('receive', 'Receive'),
        ('cancel', 'Cancel'),
    ]
    
    po = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='history')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)
    
    # Store old values for tracking changes
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'PO History'
        verbose_name_plural = 'PO Histories'
    
    def __str__(self):
        return f"{self.po.nomor_po or 'DRAFT'} - {self.get_action_display()} by {self.user} at {self.timestamp}"


class Purchase(models.Model):
    """Purchase List - Actual goods receipt (dengan atau tanpa PO)"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('received', 'Received'),
        ('verified', 'Verified'),
        ('cancelled', 'Cancelled'),
    ]
    
    nomor_purchase = models.CharField(max_length=100, unique=True, null=True, blank=True)
    supplier = models.ForeignKey('inventory.Supplier', on_delete=models.PROTECT, null=True, blank=True)
    po = models.ForeignKey(PurchaseOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchases')
    tanggal_purchase = models.DateField(null=True, blank=True, help_text="Tanggal invoice dari supplier (user harus isi manual)")
    tanggal_received = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    total_amount = models.IntegerField(default=0)  # Changed to IntegerField for easier formatting
    notes = models.TextField(blank=True, null=True)
    
    # Tracking fields
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='purchases_created'
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='purchases_received'
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='purchases_verified'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-tanggal_purchase', '-id']
        verbose_name = 'Purchase'
        verbose_name_plural = 'Purchases'
        permissions = [
            ('purchase_view', 'Can view Purchase'),
            ('purchase_warehouse', 'Can create/edit/receive Purchase (Warehouse)'),
            ('purchase_finance', 'Can verify/payment/tax invoice Purchase (Finance)'),
        ]
    
    def __str__(self):
        return f"{self.nomor_purchase or 'DRAFT'} - {self.supplier or 'No Supplier'}"
    
    def save(self, *args, **kwargs):
        # Auto-generate nomor_purchase hanya jika status bukan draft
        if self.pk and not self.nomor_purchase and self.status != 'draft':
            from django.utils import timezone
            from datetime import datetime
            # Generate nomor purchase
            date_str = datetime.now().strftime('%Y%m%d')
            # Get next ID
            last_purchase = Purchase.objects.filter(
                nomor_purchase__startswith=f'PUR-{date_str}'
            ).order_by('-nomor_purchase').first()
            
            if last_purchase and last_purchase.nomor_purchase:
                last_id = int(last_purchase.nomor_purchase.split('-')[-1])
                new_id = last_id + 1
            else:
                new_id = 1
            
            self.nomor_purchase = f"PUR-{date_str}-{new_id:04d}"
        
        # Calculate total amount
        if self.pk:
            self.total_amount = sum(item.subtotal for item in self.items.all())
        super().save(*args, **kwargs)


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT)
    quantity = models.IntegerField(default=0)
    harga_beli = models.IntegerField(default=0)  # Changed to IntegerField for easier formatting
    subtotal = models.IntegerField(default=0)  # Changed to IntegerField for easier formatting
    
    class Meta:
        ordering = ['product__nama_produk']
        unique_together = ('purchase', 'product')
    
    def __str__(self):
        return f"{self.purchase.nomor_purchase} - {self.product.sku}"
    
    def save(self, *args, **kwargs):
        # Calculate subtotal
        self.subtotal = self.quantity * self.harga_beli
        super().save(*args, **kwargs)
        # Update Purchase total
        if self.purchase.pk:
            self.purchase.save()


class PriceHistory(models.Model):
    """Track price changes for products from PO to PO"""
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='price_history')
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='price_histories', null=True, blank=True)
    purchase_order_item = models.ForeignKey(PurchaseOrderItem, on_delete=models.CASCADE, related_name='price_history', null=True, blank=True)
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='price_histories', null=True, blank=True)
    purchase_item = models.ForeignKey(PurchaseItem, on_delete=models.CASCADE, related_name='price_history', null=True, blank=True)
    
    price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.IntegerField()
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    supplier = models.ForeignKey('inventory.Supplier', on_delete=models.SET_NULL, null=True)
    
    purchase_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-purchase_date']
        verbose_name = 'Price History'
        verbose_name_plural = 'Price Histories'
        indexes = [
            models.Index(fields=['product', '-purchase_date']),
        ]
    
    def __str__(self):
        return f"{self.product.sku} - Rp {self.price} on {self.purchase_date.strftime('%Y-%m-%d')}"


class PurchasePayment(models.Model):
    """Track payments to suppliers - fokus track unpaid/remaining"""
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='payment')
    supplier = models.ForeignKey('inventory.Supplier', on_delete=models.PROTECT)
    
    # Amount tracking (using IntegerField to match Purchase)
    total_amount = models.IntegerField(default=0)  # Total dari purchase
    discount = models.IntegerField(default=0)  # Discount/potongan
    paid_amount = models.IntegerField(default=0)  # Sudah dibayar
    remaining_amount = models.IntegerField(default=0)  # Sisa yang belum dibayar
    
    # Payment dates
    due_date = models.DateTimeField()  # Jatuh tempo
    payment_date = models.DateTimeField(null=True, blank=True)  # Tanggal bayar
    
    # Status (fokus ke unpaid/remaining)
    status = models.CharField(max_length=20, choices=[
        ('unpaid', 'Unpaid'),        # Belum bayar sama sekali
        ('partial', 'Partial'),      # Sudah bayar sebagian (ada sisa)
        ('paid', 'Paid'),            # Sudah lunas
        ('overdue', 'Overdue'),      # Jatuh tempo tapi belum bayar
    ], default='unpaid')
    
    # Payment method
    payment_method = models.CharField(max_length=50, choices=[
        ('transfer', 'Transfer'),
        ('cash', 'Cash'),
        ('check', 'Check'),
        ('other', 'Other'),
    ], blank=True, null=True)
    
    # Transaction type (COD, Credit, etc.)
    transaction_type = models.CharField(max_length=50, choices=[
        ('COD', 'COD (Cash on Delivery)'),
        ('CREDIT', 'Credit'),
        ('PREPAID', 'Prepaid'),
    ], default='CREDIT', help_text="Tipe transaksi pembayaran")
    
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-due_date']
        verbose_name = 'Purchase Payment'
        verbose_name_plural = 'Purchase Payments'
        indexes = [
            models.Index(fields=['status', '-due_date']),
        ]
    
    def __str__(self):
        return f"{self.supplier.nama_supplier} - {self.purchase.nomor_purchase} - {self.get_status_display()}"
    
    def save(self, *args, **kwargs):
        # Auto-calculate paid_amount from allocations (only if pk exists)
        if self.pk:
            total_allocated = sum(alloc.amount for alloc in self.allocations.all())
            self.paid_amount = total_allocated
            
            # Update payment_date and payment_method from last allocation
            last_allocation = self.allocations.order_by('-allocation_date').first()
            if last_allocation:
                # Update payment method from last allocation
                self.payment_method = last_allocation.payment_method
                
                # Update payment_date only if fully paid
                if self.remaining_amount <= 0:
                    self.payment_date = last_allocation.allocation_date
        else:
            # For new records, set paid_amount to 0
            self.paid_amount = 0
        
        # Auto-calculate remaining amount (with discount)
        self.remaining_amount = self.total_amount - self.paid_amount - self.discount
        
        # Auto-update status
        if self.remaining_amount <= 0:
            self.status = 'paid'
        elif self.paid_amount > 0:
            self.status = 'partial'
        elif self.due_date and self.due_date < timezone.now():
            self.status = 'overdue'
        else:
            self.status = 'unpaid'
        
        super().save(*args, **kwargs)


class PurchaseTaxInvoice(models.Model):
    """Track tax invoices - fokus track yang belum dapat nomor faktur pajak"""
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='tax_invoice')
    supplier = models.ForeignKey('inventory.Supplier', on_delete=models.PROTECT)
    
    # Invoice info
    invoice_number = models.CharField(max_length=100, unique=True, blank=True, null=True)  # Nomor faktur pajak
    invoice_date = models.DateTimeField(null=True, blank=True)  # Tanggal faktur pajak
    invoice_amount = models.IntegerField(default=0)  # Total faktur
    discount = models.IntegerField(default=0)  # Discount/potongan
    
    # Tax info
    tax_amount = models.IntegerField(default=0)  # PPN
    tax_rate = models.IntegerField(default=11)  # Default 11% PPN
    subtotal = models.IntegerField(default=0)  # DPP (sebelum pajak)
    
    # Status (fokus ke belum dapat nomor faktur)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),      # Belum dapat nomor faktur pajak
        ('received', 'Received'),    # Sudah dapat nomor faktur pajak
        ('verified', 'Verified'),    # Sudah diverifikasi
        ('rejected', 'Rejected'),    # Faktur ditolak (nomor tidak valid)
    ], default='pending')
    
    # Files
    invoice_file = models.FileField(upload_to='tax_invoices/', blank=True, null=True)
    
    # Notes
    notes = models.TextField(blank=True, null=True)
    
    # Tracking
    received_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_invoices'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Purchase Tax Invoice'
        verbose_name_plural = 'Purchase Tax Invoices'
        indexes = [
            models.Index(fields=['status', '-created_at']),
        ]
    
    def __str__(self):
        if self.invoice_number:
            return f"{self.invoice_number} - {self.supplier.nama_supplier}"
        return f"Pending - {self.supplier.nama_supplier} - {self.purchase.nomor_purchase}"


class Bank(models.Model):
    """Bank accounts for payment transfers"""
    nama_bank = models.CharField(max_length=100)
    nomor_rekening = models.CharField(max_length=50)
    atas_nama = models.CharField(max_length=200, blank=True, null=True)
    
    # Link to Chart of Accounts
    account = models.ForeignKey(
        'finance.Account',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='banks',
        help_text="Link ke akun di Chart of Accounts untuk pencatatan akuntansi"
    )
    
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['nama_bank']
        verbose_name = 'Bank'
        verbose_name_plural = 'Banks'
    
    def __str__(self):
        return f"{self.nama_bank} - {self.nomor_rekening}"
    
    @property
    def account_name(self):
        """Get account name if linked"""
        return f"{self.account.code} - {self.account.name}" if self.account else "Belum di-link"
    
    @property
    def current_balance(self):
        """Get current balance from linked account"""
        return self.account.current_balance if self.account else 0


class PurchasePaymentAllocation(models.Model):
    """Track payment allocations for each purchase payment"""
    payment = models.ForeignKey(PurchasePayment, on_delete=models.CASCADE, related_name='allocations')
    
    # Allocation details (using IntegerField to match PurchasePayment)
    amount = models.IntegerField(default=0)  # Amount allocated
    allocation_date = models.DateTimeField(default=timezone.now)  # When this allocation was made
    
    # Payment method for this allocation
    payment_method = models.CharField(max_length=50, choices=[
        ('transfer', 'Transfer'),
        ('cash', 'Cash'),
        ('check', 'Check'),
        ('other', 'Other'),
    ], blank=True, null=True)
    
    # Transfer from (if payment method is transfer)
    transfer_from = models.ForeignKey(Bank, on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_allocations')
    
    # Reference
    reference_number = models.CharField(max_length=100, blank=True, null=True)  # No. transfer, check, etc.
    
    # Notes
    notes = models.TextField(blank=True, null=True)
    
    # Tracking
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='payment_allocations'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-allocation_date']
        verbose_name = 'Payment Allocation'
        verbose_name_plural = 'Payment Allocations'
    
    def __str__(self):
        return f"Allocation {self.amount} to {self.payment.purchase.nomor_purchase} on {self.allocation_date.strftime('%Y-%m-%d')}"
