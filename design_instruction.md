# Panduan Design System ERP Alfa

Dokumen ini berisi panduan lengkap untuk design system yang digunakan di proyek ERP Alfa. Setiap komponen UI harus mengikuti standar ini untuk menjaga konsistensi visual.

## 🎨 **Modern Design System**

### 1. **Glassmorphism Style**
**Definisi:** Efek kaca buram dengan transparansi dan blur yang memberikan kedalaman visual.

**CSS Variables:**
```css
:root {
  --glass-bg: rgba(255, 255, 255, 0.95);
  --glass-blur: blur(10px);
  --glass-border: 1px solid rgba(255, 255, 255, 0.2);
  --glass-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
}
```

**Implementasi:**
```css
.glass-card {
  background: var(--glass-bg);
  backdrop-filter: var(--glass-blur);
  border: var(--glass-border);
  box-shadow: var(--glass-shadow);
  border-radius: 20px;
}
```

### 2. **Gradient Backgrounds**
**Primary Gradient (Login/Modern Pages):**
```css
--primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
```

**Secondary Gradient (Cards/Hover):**
```css
--secondary-gradient: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
```

**Usage:**
```css
.modern-bg {
  background: var(--primary-gradient);
  min-height: 100vh;
}
```

### 3. **Modern Card Design**
**Standard Card:**
```css
.modern-card {
  background: var(--glass-bg);
  backdrop-filter: var(--glass-blur);
  border-radius: 20px;
  border: none;
  box-shadow: 0 4px 15px rgba(0,0,0,0.1);
  transition: all 0.3s ease;
}

.modern-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.3);
}
```

### 4. **Button Styles**
**Primary Button:**
```css
.btn-modern-primary {
  background: var(--primary-gradient);
  border: none;
  border-radius: 12px;
  padding: 12px 24px;
  font-weight: 600;
  color: white;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
  transition: all 0.3s ease;
}

.btn-modern-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.5);
  color: white;
}
```

**Secondary Button:**
```css
.btn-modern-secondary {
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(102, 126, 234, 0.3);
  border-radius: 12px;
  padding: 12px 24px;
  font-weight: 600;
  color: #667eea;
  transition: all 0.3s ease;
}

.btn-modern-secondary:hover {
  background: rgba(102, 126, 234, 0.1);
  transform: translateY(-1px);
}
```

### 5. **Form Input Styles**
**Modern Input Group:**
```css
.input-group-modern {
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.input-group-modern .form-control {
  border: 1px solid #dee2e6;
  border-left: none;
  padding: 12px 15px;
  font-size: 1rem;
}

.input-group-modern .form-control:focus {
  border-color: #667eea;
  box-shadow: 0 0 0 0.2rem rgba(102, 126, 234, 0.25);
}

.input-group-modern .input-group-text {
  border: 1px solid #dee2e6;
  background-color: #f8f9fa;
  border-right: none;
}
```

### 6. **Typography**
**Headings:**
```css
.modern-heading {
  font-weight: 700;
  color: #2d3748;
  letter-spacing: 0.5px;
}

.modern-subtitle {
  color: #718096;
  font-weight: 500;
}
```

### 7. **Micro-interactions & Animations**
**Loading Spinner:**
```css
.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
```

**Hover Effects:**
```css
.hover-lift {
  transition: all 0.3s ease;
}

.hover-lift:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
}
```

### 8. **Color Palette**
**Primary Colors:**
```css
:root {
  --primary-blue: #667eea;
  --primary-purple: #764ba2;
  --primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  
  --success-green: #48bb78;
  --warning-yellow: #ed8936;
  --danger-red: #f56565;
  --info-blue: #4299e1;
}
```

**Neutral Colors:**
```css
:root {
  --text-primary: #2d3748;
  --text-secondary: #718096;
  --text-muted: #a0aec0;
  
  --bg-primary: #ffffff;
  --bg-secondary: #f7fafc;
  --bg-muted: #edf2f7;
}
```

## 📱 **Mobile-First Design**

### 1. **Responsive Breakpoints**
```css
/* Mobile First */
@media (max-width: 576px) {
  .container-fluid {
    padding: 15px;
  }
  
  .card {
    margin: 10px;
    border-radius: 15px;
  }
}

/* Tablet */
@media (min-width: 577px) and (max-width: 768px) {
  .card {
    max-width: 500px;
    margin: 20px auto;
  }
}

/* Desktop */
@media (min-width: 769px) {
  .card {
    max-width: 450px;
  }
}
```

### 2. **Touch-Friendly Elements**
```css
.touch-friendly {
  min-height: 44px;
  min-width: 44px;
  padding: 12px 16px;
  font-size: 16px; /* Prevent zoom on iOS */
}
```

## 🎯 **Implementation Guidelines**

### 1. **Login Pages**
**Template Structure:**
```html
<div class="container-fluid d-flex justify-content-center align-items-center" 
     style="min-height: 100vh; background: var(--primary-gradient);">
  <div class="card modern-card" style="width: 100%; max-width: 450px;">
    <!-- Content -->
  </div>
</div>
```

### 2. **Dashboard Cards**
**Template Structure:**
```html
<div class="row g-4">
  <div class="col-md-6 col-lg-4">
    <div class="card modern-card hover-lift">
      <div class="card-body">
        <!-- Content -->
      </div>
    </div>
  </div>
</div>
```

### 3. **Form Components**
**Template Structure:**
```html
<div class="mb-4">
  <label class="form-label fw-semibold text-dark">
    <i class="bi bi-person-fill me-2"></i>Label
  </label>
  <div class="input-group input-group-modern">
    <span class="input-group-text">
      <i class="bi bi-person text-muted"></i>
    </span>
    <input type="text" class="form-control">
  </div>
</div>
```

## 🚀 **Best Practices**

### 1. **Consistency**
- **Selalu gunakan CSS variables** untuk warna dan spacing
- **Ikuti naming convention** yang konsisten
- **Gunakan icon Bootstrap** untuk konsistensi visual

### 2. **Performance**
- **Minimize CSS** dengan menggunakan utility classes
- **Optimize images** untuk mobile
- **Use CSS transforms** untuk animasi (lebih smooth)

### 3. **Accessibility**
- **Proper contrast ratios** (minimum 4.5:1)
- **Keyboard navigation** support
- **Screen reader** friendly labels

### 4. **Mobile Optimization**
- **Touch targets** minimum 44px
- **Font size** minimum 16px untuk input
- **Viewport meta tag** selalu ada

## 📋 **Checklist Implementation**

Sebelum deploy, pastikan:
- [ ] CSS variables sudah didefinisikan
- [ ] Responsive breakpoints sudah benar
- [ ] Touch-friendly elements sudah sesuai
- [ ] Loading states sudah diimplementasi
- [ ] Error states sudah dihandle
- [ ] Accessibility sudah diperhatikan
- [ ] Performance sudah dioptimasi

---

**Note:** Design system ini adalah living document yang akan diupdate sesuai kebutuhan proyek. Setiap perubahan harus didokumentasikan di sini. 