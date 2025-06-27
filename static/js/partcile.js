
        //        // Initialize elements
        const chatbox = document.getElementById('chatbox');
        const messageInput = document.getElementById('message');
        const fileInput = document.getElementById('file');
        const fileInfo = document.getElementById('fileInfo');
        const sendButton = document.getElementById('sendButton');
        
        let selectedFiles = [];

        // Initialize particles.js with custom config
        particlesJS('particles-js', {
            particles: {
                number: {
                    value: 50,
                    density: {
                        enable: true,
                        value_area: 800
                    }
                },
                color: {
                    value: '#6366f1'
                },
                shape: {
                    type: 'circle'
                },
                opacity: {
                    value: 0.5,
                    random: false,
                    anim: {
                        enable: false
                    }
                },
                size: {
                    value: 3,
                    random: true,
                    anim: {
                        enable: false
                    }
                },
                line_linked: {
                    enable: true,
                    distance: 150,
                    color: '#6366f1',
                    opacity: 0.2,
                    width: 1
                },
                move: {
                    enable: true,
                    speed: 2,
                    direction: 'none',
                    random: false,
                    straight: false,
                    out_mode: 'out',
                    bounce: false,
                    attract: {
                        enable: false
                    }
                }
            },
            interactivity: {
                detect_on: 'canvas',
                events: {
                    onhover: {
                        enable: true,
                        mode: 'grab'
                    },
                    onclick: {
                        enable: true,
                        mode: 'push'
                    },
                    resize: true
                },
                modes: {
                    grab: {
                        distance: 140,
                        line_linked: {
                            opacity: 0.5
                        }
                    },
                    push: {
                        particles_nb: 4
                    }
                }
            },
            retina_detect: true
        });

        // File handling
        fileInput.addEventListener('change', function() {
            selectedFiles = Array.from(fileInput.files);
            updateFileInfo();
        });

        function updateFileInfo() {
            if (selectedFiles.length > 0) {
                const fileNames = selectedFiles.map(file => file.name).join(', ');
                fileInfo.innerHTML = `
                    <div class="file-info">
                        <i class="fas fa-file"></i>
                        <span>${selectedFiles.length} file(s) selected: ${fileNames}</span>
                        <i class="fas fa-times close-file" onclick="clearFiles()"></i>
                    </div>
                `;
            } else {
                fileInfo.innerHTML = '';
            }
        }

        function clearFiles() {
            selectedFiles = [];
            fileInput.value = '';
            updateFileInfo();
        }

        // Get current time
        function getCurrentTime() {
            const now = new Date();
            return now.toLocaleTimeString('en-US', { 
                hour: 'numeric', 
                minute: '2-digit',
                hour12: true 
            });
        }

        // Create message element
        function createMessage(content, isUser = false) {
            const messageWrapper = document.createElement('div');
            messageWrapper.className = `message-wrapper ${isUser ? 'user' : 'bot'}`;
            
            messageWrapper.innerHTML = `
                <div class="avatar ${isUser ? 'user' : 'bot'}">
                    <i class="fas fa-${isUser ? 'user' : 'robot'}"></i>
                </div>
                <div class="message-content">
                    <div class="message-info">
                        <span>${isUser ? 'You' : 'AI Assistant'}</span>
                        <span>•</span>
                        <span class="timestamp">${getCurrentTime()}</span>
                    </div>
                    <div class="message ${isUser ? 'user' : 'bot'}">
                        ${content}
                    </div>
                </div>
            `;
            
            return messageWrapper;
        }

        // Create typing indicator
        function createTypingIndicator() {
            const wrapper = document.createElement('div');
            wrapper.className = 'message-wrapper bot';
            wrapper.id = 'typing-indicator';
            
            wrapper.innerHTML = `
                <div class="avatar bot">
                    <i class="fas fa-robot"></i>
                </div>
                <div class="message-content">
                    <div class="message-info">
                        <span>AI Assistant</span>
                        <span>•</span>
                        <span class="timestamp">Typing...</span>
                    </div>
                    <div class="typing-indicator">
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                    </div>
                </div>
            `;
            
            return wrapper;
        }

        // Scroll to bottom smoothly
        function scrollToBottom() {
            setTimeout(() => {
                chatbox.scrollTo({
                    top: chatbox.scrollHeight,
                    behavior: 'smooth'
                });
            }, 100);
        }

        // Send message
        async function sendMessage() {
            const message = messageInput.value.trim();
            
            if (!message && selectedFiles.length === 0) {
                return;
            }

            // Create form data
            const formData = new FormData();
            
            if (message) {
                formData.append('message', message);
                // Add user message to chat
                chatbox.appendChild(createMessage(message, true));
                messageInput.value = '';
            }
            
            if (selectedFiles.length > 0) {
                selectedFiles.forEach(file => {
                    formData.append('file', file);
                });
                
                // Add file upload message
                const fileMessage = `Uploaded ${selectedFiles.length} file(s): ${selectedFiles.map(f => f.name).join(', ')}`;
                if (!message) {
                    chatbox.appendChild(createMessage(fileMessage, true));
                }
                
                clearFiles();
            }

            // Show typing indicator
            const typingIndicator = createTypingIndicator();
            chatbox.appendChild(typingIndicator);
            scrollToBottom();

            try {
                // Simulate API delay for demo (remove in production)
                await new Promise(resolve => setTimeout(resolve, 1000));

                const response = await axios.post('/chat', formData, {
                    headers: {
                        'Content-Type': 'multipart/form-data'
                    },
                    timeout: 30000 // 30 second timeout
                });

                // Remove typing indicator
                typingIndicator.remove();

                // Add bot response
                const botResponse = response.data.response || "I'm sorry, I couldn't process that request.";
                chatbox.appendChild(createMessage(botResponse, false));

            } catch (error) {
                console.error('Error:', error);
                
                // Remove typing indicator
                typingIndicator.remove();

                // Show error message
                let errorMessage = "I apologize, but I encountered an error. Please try again.";
                
                if (error.code === 'ECONNABORTED') {
                    errorMessage = "The request timed out. Please try again with a shorter message or smaller files.";
                } else if (error.response && error.response.status === 413) {
                    errorMessage = "The file size is too large. Please try with smaller files.";
                }

                chatbox.appendChild(createMessage(errorMessage, false));
            }

            scrollToBottom();
        }

        // Event listeners
        sendButton.addEventListener('click', sendMessage);

        messageInput.addEventListener('keydown', async function(event) {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                await sendMessage();
            }
        });

        // Auto-resize input (optional feature)
        messageInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        });

        // Welcome animation
        window.addEventListener('load', () => {
            scrollToBottom();
        });

        // Handle visibility change to update status
        document.addEventListener('visibilitychange', () => {
            const statusDot = document.querySelector('.status-dot');
            const statusText = document.querySelector('.status-indicator span:last-child');
            
            if (document.hidden) {
                statusDot.style.backgroundColor = '#6b7280';
                if (statusText) statusText.textContent = 'Away';
            } else {
                statusDot.style.backgroundColor = '#10b981';
                if (statusText) statusText.textContent = 'Online';
            }
        });

        // Add keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + / to focus input
            if ((e.ctrlKey || e.metaKey) && e.key === '/') {
                e.preventDefault();
                messageInput.focus();
            }
        });

        // Mobile viewport height fix
        function setViewportHeight() {
            const vh = window.innerHeight * 0.01;
            document.documentElement.style.setProperty('--vh', `${vh}px`);
        }

        setViewportHeight();
        window.addEventListener('resize', setViewportHeight);

        // Add CSS for mobile viewport
        const style = document.createElement('style');
        style.textContent = `
            @media (max-width: 768px) {
                .main-container {
                    height: calc(var(--vh, 1vh) * 100);
                }
            }
        `;
        document.head.appendChild(style);