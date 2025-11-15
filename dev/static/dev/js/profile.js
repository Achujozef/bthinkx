/* ============================================
   Profile Page JavaScript
   ============================================ */

// Tab Switching
function switchTab(btn, tabId) {
    // Remove active class from all tabs and contents
    document.querySelectorAll('.profile-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });

    // Add active class to clicked tab and corresponding content
    btn.classList.add('active');
    document.getElementById(tabId).classList.add('active');
}

// Edit Profile Modal
function openEditModal() {
    // Get current values from the page (from user info in DOM)
    // If not present, set to empty strings
    const getVal = (selector, def = "") => {
        const el = document.querySelector(selector);
        return el ? (el.value !== undefined ? el.value : el.textContent) : def;
    };

    const currentFirstName =
        getVal('[name="first_name"]') ||
        getVal(".profile-name", "").split(" ")[0] ||
        "";
    const currentLastName =
        getVal('[name="last_name"]') ||
        ((getVal(".profile-name", "").split(" ").slice(1).join(" ")) || "");
    const currentEmail =
        getVal('[name="email"]') ||
        (document.querySelector(".about-item .about-value")
            ? document.querySelectorAll(".about-item .about-value")[1].textContent.trim()
            : "");
    const currentPhone =
        getVal('[name="phone"]') ||
        (document.querySelector(".about-item .about-value:nth-child(3)")
            ? document.querySelectorAll(".about-item .about-value")[2].textContent.trim()
            : "");
    // Try address from about tab fallback to blank
    let currentAddress = "";
    let addrEl = document.querySelector('span.profile-meta-item i.bi-geo-alt-fill');
    if (addrEl && addrEl.parentElement && addrEl.parentElement.querySelector('span')) {
        currentAddress = addrEl.parentElement.querySelector("span").textContent.trim();
    } else {
        // try about section
        const labelNodes = Array.from(document.querySelectorAll('.about-label'));
        const addressNode = labelNodes.find(n => n.textContent.trim() === "Address");
        if (addressNode && addressNode.parentElement) {
            const v = addressNode.parentElement.querySelector('.about-value');
            currentAddress = v ? v.textContent.trim() : "";
        }
    }
    // Emergency Contact not shown, always blank
    const currentEmergency = "";

    // CSRF token from input[name=csrfmiddlewaretoken] if present
    let csrf = "";
    const csrfEl = document.querySelector('input[name=csrfmiddlewaretoken]');
    if (csrfEl) {
        csrf = csrfEl.value;
    }

    // Prepare modal HTML with filled values
    const modal = document.createElement('div');
    modal.className = 'edit-modal';
    modal.innerHTML = `
        <div class="edit-modal-content">
            <div class="edit-modal-header">
                <h2>Edit Profile</h2>
                <button onclick="this.closest('.edit-modal').remove()" class="close-btn">
                    <i class="bi bi-x-lg"></i>
                </button>
            </div>
            <form method="POST" enctype="multipart/form-data" class="edit-form">
                <input type="hidden" name="csrfmiddlewaretoken" value="${csrf}">
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">First Name</label>
                        <input type="text" name="first_name" class="form-control" value="${currentFirstName.replace(/"/g, "&quot;")}" required>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Last Name</label>
                        <input type="text" name="last_name" class="form-control" value="${currentLastName.replace(/"/g, "&quot;")}" required>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Email</label>
                        <input type="email" class="form-control" value="${currentEmail.replace(/"/g, "&quot;")}" disabled>
                        <small style="color: var(--text-muted); margin-top: 4px;">Email cannot be changed</small>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Phone Number</label>
                        <input type="tel" name="phone" class="form-control" value="${currentPhone.replace(/"/g, "&quot;")}">
                    </div>
                </div>
                <div class="form-group">
                    <label class="form-label">Address</label>
                    <input type="text" name="address" class="form-control" value="${currentAddress.replace(/"/g, "&quot;")}">
                </div>
                <div class="form-group">
                    <label class="form-label">Emergency Contact</label>
                    <input type="text" name="emergency_contact" class="form-control" value="${currentEmergency.replace(/"/g, "&quot;")}" placeholder="Name and phone number">
                </div>
                <div class="form-group">
                    <label class="form-label">Profile Avatar</label>
                    <input type="file" name="avatar" class="form-control" accept="image/*">
                    <small style="color: var(--text-muted); margin-top: 4px;">Supported formats: JPG, PNG, GIF (Max 5MB)</small>
                </div>
                <div class="modal-footer">
                    <button type="button" onclick="this.closest('.edit-modal').remove()" class="btn-secondary">Cancel</button>
                    <button type="submit" class="btn-primary">Save Changes</button>
                </div>
            </form>
        </div>
    `;
    document.body.appendChild(modal);
    modal.querySelectorAll('.edit-form')[0].addEventListener('submit', function(e) {
        // Form will submit normally to Django view
    });
}

// Avatar Upload
function uploadAvatar(input) {
    if (input.files && input.files[0]) {
        const file = input.files[0];

        // Size validation
        if (file.size > 5 * 1024 * 1024) {
            alert('File size exceeds 5MB limit');
            return;
        }

        // Type validation
        if (!['image/jpeg', 'image/png', 'image/gif'].includes(file.type)) {
            alert('Only JPG, PNG, and GIF files are supported');
            return;
        }

        // Preview
        const reader = new FileReader();
        reader.onload = function(e) {
            const img = document.querySelector('.profile-avatar');
            if (img) img.src = e.target.result;
        };
        reader.readAsDataURL(file);

        // Create form
        const form = document.createElement('form');
        form.method = 'POST';
        form.enctype = 'multipart/form-data';

        // Inject CSRF token
        const csrf = document.getElementById('csrfToken').value;
        const csrfField = document.createElement('input');
        csrfField.type = 'hidden';
        csrfField.name = 'csrfmiddlewaretoken';
        csrfField.value = csrf;
        form.appendChild(csrfField);

        // action field
        const actionField = document.createElement('input');
        actionField.type = 'hidden';
        actionField.name = 'action';
        actionField.value = 'upload_avatar';
        form.appendChild(actionField);

        // File input
        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.name = 'avatar';
        fileInput.files = input.files;
        form.appendChild(fileInput);

        document.body.appendChild(form);
        form.submit(); 
        form.remove();
    }
}
   
