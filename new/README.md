# 时光胶囊 (Time Capsule)

A web application that allows users to have a conversation with their 20-year-old self, built with modern HTML, CSS, and JavaScript for the frontend and Sanic for the backend.

## Features

- **Modern, warm UI**: Light yellow theme with accessible design
- **Elder-friendly**: Large text, high contrast mode, simple navigation
- **Responsive design**: Works on all devices
- **Accessibility features**: Font size controls, high contrast mode, keyboard navigation

## Project Structure

```
new/
├── app.py                # Sanic server
├── requirements.txt      # Python dependencies
├── static/               # Static assets
│   ├── css/              # CSS stylesheets
│   ├── js/               # JavaScript files
│   └── images/           # Images and icons
└── templates/            # HTML templates
```

## Setup and Installation

1. Clone the repository
2. Install the requirements:
   ```
   pip install -r new/requirements.txt
   ```
3. Run the application:
   ```
   cd new
   python app.py
   ```
4. Access the application at `http://localhost:8080`

## Technologies Used

- **Frontend**: HTML5, CSS3, JavaScript (ES6+)
- **CSS Framework**: Bootstrap 5
- **Icons**: Font Awesome
- **Backend**: Sanic (Python)

## Design Considerations

This application is specifically designed for elderly users with:

- Larger font sizes by default
- High color contrast options
- Simple, intuitive navigation
- Clear visual hierarchy
- Warm, calming color scheme
- Consistent UI across all pages

## License

All rights reserved. 