// Анимация перехода между уроками
document.querySelectorAll('.lesson-card').forEach(card => {
    card.addEventListener('mouseenter', () => {
        card.style.transform = 'translateY(-5px)';
        card.style.boxShadow = '0 5px 15px rgba(0,0,0,0.1)';
    });
    
    card.addEventListener('mouseleave', () => {
        card.style.transform = '';
        card.style.boxShadow = '';
    });
});

// Обработка завершения урока (будем развивать позже)
document.getElementById('complete-btn')?.addEventListener('click', async () => {
    const response = await fetch('/api/complete-lesson/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({lesson_id: currentLessonId})
    });
    
    if (response.ok) {
        alert('Урок завершен!');
    }
});

function getCookie(name) {
    // Функция для получения CSRF-токена
}