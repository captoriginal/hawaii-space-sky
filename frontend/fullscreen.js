/**
 * Full-screen image modal functionality
 *
 * Provides a simple API to show images in full-screen mode.
 */

let modal = null;
let modalImg = null;
let closeButton = null;
let initialized = false;

// Initialize modal elements
function initModal() {
  if (initialized) return;

  modal = document.getElementById('fullscreen-modal');
  if (!modal) {
    console.error('Fullscreen modal element not found');
    return;
  }

  modalImg = modal.querySelector('img');
  closeButton = modal.querySelector('.close-button');

  // Event listeners for closing the modal
  if (closeButton) {
    closeButton.addEventListener('click', (e) => {
      e.stopPropagation();
      closeFullscreen();
    });
  }

  modal.addEventListener('click', (e) => {
    // Only close if clicking the backdrop, not the image
    if (e.target === modal) {
      closeFullscreen();
    }
  });

  // ESC key to close
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal && modal.classList.contains('active')) {
      closeFullscreen();
    }
  });

  initialized = true;
}

// Auto-initialize when module loads (defer ensures DOM is ready)
setTimeout(initModal, 0);

/**
 * Opens an image in full-screen mode
 * @param {string} src - The image source URL
 * @param {string} alt - The alt text for the image
 */
export function openFullscreen(src, alt = '') {
  if (!src || !modal || !modalImg) return;

  modalImg.src = src;
  modalImg.alt = alt;
  modal.classList.add('active');

  // Prevent body scroll when modal is open
  document.body.style.overflow = 'hidden';
}

/**
 * Closes the full-screen modal
 */
export function closeFullscreen() {
  if (!modal) return;

  modal.classList.remove('active');

  // Restore body scroll
  document.body.style.overflow = '';

  // Clear image after transition
  setTimeout(() => {
    if (modalImg && !modal.classList.contains('active')) {
      modalImg.src = '';
      modalImg.alt = '';
    }
  }, 300);
}

/**
 * Makes an image element clickable to open in full-screen
 * @param {HTMLImageElement} imgElement - The image element to make clickable
 */
export function makeImageFullscreenable(imgElement) {
  if (!imgElement) return;

  // Ensure modal is initialized
  if (!initialized) {
    initModal();
  }

  imgElement.addEventListener('click', () => {
    openFullscreen(imgElement.src, imgElement.alt);
  });
}
