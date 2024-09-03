import sys
from datetime import datetime
from threading import Thread

import configparser
from openai import OpenAI
from PyQt5 import QtWidgets, QtGui, QtCore

from test_api import is_api_key_valid

ai_models = [
    {'id': 'gpt-3.5-turbo-16k', 'name': 'GPT-3.5 Turbo 16k', 'max_tokens': 16381},
    {'id': 'gpt-4o', 'name': 'GPT-4o', 'max_tokens': 4095},
]

class ChatTab(QtWidgets.QWidget):
    # create a chat completion signal
    chat_completion_signal = QtCore.pyqtSignal(str)

    def __init__(self, api_key):
        '''Chat tab widget constructor'''
        super().__init__()

        # connect the signal to the display_message slot
        self.chat_completion_signal.connect(self.display_ai_response)

        # UI configuration
        self.selected_model = ai_models[0]['id']
        self.api_key = api_key
        self.client = OpenAI(
            api_key = self.api_key
        )
        self.messages = [
            {"role": "system", "content": "Your are a helpful assistant."}
        ]

        # log
        self.chat_log_label = QtWidgets.QLabel("Chat Log:")
        self.chat_log = QtWidgets.QTextEdit(self)
        self.chat_log.setReadOnly(True)

        # input
        self.chat_input_label = QtWidgets.QLabel("Chat Input:")
        self.chat_input = QtWidgets.QTextEdit(self)
        self.chat_input.installEventFilter(self)

        # model selection radio boxes
        self.model_group_box = QtWidgets.QGroupBox("Model Selection")
        self.model_group_box_layout = QtWidgets.QVBoxLayout(self.model_group_box)

        for index, model in enumerate(ai_models):
            radio_button = QtWidgets.QRadioButton(model['name'])
            radio_button.setChecked(model['id'] == self.selected_model)
            radio_button.toggled.connect(self.model_radio_button_toggled)
            self.model_group_box_layout.addWidget(radio_button)
            ai_models[index]['radio_button'] = radio_button

        # temperature and max tokens
        self.temperature_label = QtWidgets.QLabel("Temperature:")
        self.temperature_input = QtWidgets.QLineEdit("0.5", self)

        self.max_tokens_label = QtWidgets.QLabel("Max Tokens:")
        self.max_tokens_input = QtWidgets.QLineEdit(str(ai_models[0]['max_tokens']), self)
        self.max_tokens_input.textEdited.connect(self.max_tokens_slider_set_value)

        self.max_tokens_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.max_tokens_slider.valueChanged.connect(self.max_tokens_input_set_value)
        self.max_tokens_slider.setMinimum(1)
        self.max_tokens_slider.setMaximum(ai_models[0]['max_tokens'])
        self.max_tokens_slider.setValue(1000)

        # action buttons
        send_icon = QtGui.QIcon("resources/send.png")
        self.send_button = QtWidgets.QPushButton(send_icon, "Send", self)
        self.send_button.clicked.connect(self.send_message)

        export_icon = QtGui.QIcon("resources/export.png")
        self.export_button = QtWidgets.QPushButton(export_icon, "Export Chat", self)
        self.export_button.clicked.connect(self.export_chat)

        # add all to the layout
        layout = QtWidgets.QVBoxLayout(self)
        self.setLayout(layout)
        layout.addWidget(self.chat_log_label)
        layout.addWidget(self.chat_log)
        layout.addWidget(self.chat_input_label)
        layout.addWidget(self.chat_input)
        layout.addWidget(self.model_group_box)
        layout.addWidget(self.temperature_label)
        layout.addWidget(self.temperature_input)
        layout.addWidget(self.max_tokens_label)
        layout.addWidget(self.max_tokens_slider)
        layout.addWidget(self.max_tokens_input)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self.send_button)
        button_layout.addWidget(self.export_button)

        layout.addLayout(button_layout)

    def eventFilter(self, obj, event):
        '''Event filter to send message on pressing Enter key'''
        if obj is self.chat_input and event.type() == QtCore.QEvent.KeyPress:
            if event.key() == QtCore.Qt.Key_Return and event.modifiers() != QtCore.Qt.ShiftModifier:
                self.send_message()
                return True
        return super().eventFilter(obj, event)

    def showEvent(self, event):
        '''Focus on chat input when the window is shown'''
        super().showEvent(event)
        self.chat_input.setFocus()

    def max_tokens_input_set_value(self, value):
        '''Set the value of the max tokens slider when the input is edited'''
        self.max_tokens_input.setText(str(value))

    def max_tokens_slider_set_value(self):
        '''Set the value of the max tokens input when the slider is moved'''
        try:
            self.max_tokens_slider.setValue(int(self.max_tokens_input.text()))
        except:
            pass

    def model_radio_button_toggled(self):
        '''Set the selected model when a radio button is toggled'''
        for model in ai_models:
            if model['radio_button'].isChecked():
                self.selected_model = model['id']
                max_tokens = min(model['max_tokens'], self.max_tokens_slider.value())
                self.max_tokens_slider.setMaximum(model['max_tokens'])
                self.max_tokens_slider.setValue(max_tokens)
                self.max_tokens_input.setText(str(max_tokens))

    def display_ai_response(self, text):
        '''Display the message in the chat log'''
        response_cursor = self.chat_log.textCursor()
        response_cursor.movePosition(QtGui.QTextCursor.End)
        response_cursor.insertText('-' * 40 + '\n')
        response_cursor.insertHtml("<span style='color: red'>GPT: </span>")
        response_cursor.insertText(f"{text}\n\n")
        # scroll to the bottom
        self.chat_log.moveCursor(QtGui.QTextCursor.End)

    def send_prompt_thread(self, max_tokens, temperature):
        '''Send the message to the API in a separate thread'''
        try:
            chat_completion = self.client.chat.completions.create(
                messages=self.messages,
                model=self.selected_model,
                max_tokens=max_tokens,
                temperature=temperature
            )
            response_text = chat_completion.choices[0].message.content
            self.messages.append({"role": "assistant", "content": f"{response_text}\n"})
            self.chat_completion_signal.emit(response_text)
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            QtWidgets.QMessageBox.critical(self, "API Error", error_msg)

    def send_message(self):
        '''Send the message to the API'''
        message = self.chat_input.toPlainText().strip()
        if not message:
            return
        self.chat_input.clear()
        self.chat_log.setReadOnly(True)

        user_cursor = self.chat_log.textCursor()
        user_cursor.movePosition(QtGui.QTextCursor.End)
        user_cursor.insertText('-' * 40 + '\n')
        user_cursor.insertHtml("<span style='color: blue'>You: </span>")
        user_cursor.insertText(f"\n{message}\n\n")

        max_tokens = int(self.max_tokens_input.text())
        temperature = float(self.temperature_input.text())
        if temperature < 0:
            QtWidgets.QMessageBox.warning(
                self,
                "Invalid Temperature",
                "Please enter a valid temperature value greater than 0.",
            )
            return
        self.messages.append({"role": "user", "content": f"{message}\n"})
        # create a new thread to send the message
        chat_thread = Thread(target=self.send_prompt_thread, args=(max_tokens, temperature))
        chat_thread.start()

    def export_chat(self):
        '''Export the chat log to a text file'''
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d-%H-%M-%S")
        file_name = f"chat_{timestamp}.txt"

        try:
            with open(file_name, "w") as f:
                f.write(self.chat_log.toPlainText())
            QtWidgets.QMessageBox.information(
                self, "Export Successful", f"The chat has been exported to {file_name}."
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Export Error",
                f"An error occurred while exporting the chat: {str(e)}",
            )


class ChatWindow(QtWidgets.QWidget):
    def __init__(self):
        '''Chat window constructor'''
        super().__init__()

        self.setWindowTitle("GUI-GPT")
        self.setGeometry(50, 50, 800, 600)
        self.setWindowIcon(QtGui.QIcon("resources/icon.png"))

        self.tab_widget = QtWidgets.QTabWidget(self)
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.tabCloseRequested.connect(self.check_tab_count)

        tab_icon = QtGui.QIcon("resources/tab.png")
        self.new_tab_button = QtWidgets.QPushButton(tab_icon, "New Chat Tab", self)
        self.new_tab_button.clicked.connect(self.add_new_tab)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.tab_widget)
        layout.addWidget(self.new_tab_button)

        self.tab_count = 0
        self.add_new_tab()

        self.showMaximized()

    def add_new_tab(self):
        '''Add a new chat tab'''
        self.tab_count += 1
        api_key = self.get_api_key()
        if api_key:
            chat_tab = ChatTab(api_key)
            index = self.tab_widget.addTab(chat_tab, f"Chat {self.tab_count}")
            self.tab_widget.setCurrentIndex(index)

    def close_tab(self, index):
        '''Close the chat tab'''
        widget = self.tab_widget.widget(index)
        if widget is not None:
            widget.deleteLater()
            self.tab_widget.removeTab(index)

    def check_tab_count(self):
        '''Check the number of tabs and close the application if there are no tabs'''
        if self.tab_widget.count() == 0:
            QtWidgets.QApplication.quit()

    def get_api_key(self):
        '''Get the OpenAI API key from the user'''
        config = configparser.ConfigParser()
        config.read("config.ini")
        api_key = config.get("API", "key", fallback="")
        while not api_key or not is_api_key_valid(api_key):
            api_key, ok = QtWidgets.QInputDialog.getText(
                self,
                "OpenAI API Key",
                "Enter your OpenAI API key:",
                QtWidgets.QLineEdit.Normal,
                "",
            )
            if not ok:
                sys.exit()
            if is_api_key_valid(api_key):
                config["API"] = {"key": api_key}
                with open("config.ini", "w") as configfile:
                    config.write(configfile)
            else:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Invalid API Key",
                    "The API key you entered is invalid. Please try again.",
                )
        return api_key


app = QtWidgets.QApplication([])
window = ChatWindow()

app_icon = QtGui.QIcon("resources/icon.png")
app.setWindowIcon(app_icon)

window.show()
app.exec_()
