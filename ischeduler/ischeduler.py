#!/usr/bin/env python

import tkinter
from time import sleep

textFont1 = ("Arial", 10, "bold italic")
textFont2 = ("Arial", 16, "bold")
textFont3 = ("Arial", 8, "bold")


class LabelWidget(tkinter.Entry):
    def __init__(self, master, x, y, text):
        self.text = tkinter.StringVar()
        self.text.set(text)
        tkinter.Entry.__init__(self, master=master)
        self.config(relief="ridge", font=textFont1,
                    bg="#ffffff000", fg="#000000fff",
                    readonlybackground="#ffffff000",
                    justify='center',
                    highlightthickness=0,
                    # width=8,
                    textvariable=self.text,
                    state="readonly")
        self.grid(column=x, row=y, padx=0, pady=0, sticky=tkinter.W+tkinter.E+tkinter.S+tkinter.N)


class EntryWidget(tkinter.Entry):
    def __init__(self, master, x, y):
        tkinter.Entry.__init__(self, master=master)
        self.value = tkinter.StringVar()
        self.config(textvariable=self.value,
                    # width=8,
                    relief="ridge",
                    font=textFont1,
                    bg="#ddddddddd", fg="#000000000",
                    highlightthickness=0,
                    justify='center')
        self.grid(column=x, row=y, padx=0, pady=0, sticky=tkinter.W+tkinter.E+tkinter.S+tkinter.N)
        self.value.set("")


class EntryGrid(tkinter.Tk):
    ''' Dialog box with Entry widgets arranged in columns and rows.'''
    def __init__(self, colList, rowList, title="Irrigator"):
        self.cols = colList[:]
        self.colList = colList[:]
        self.colList.insert(0, "")
        self.rowList = rowList
        tkinter.Tk.__init__(self)
        self.title(title)

        self.commands_frame = tkinter.Frame(self, bg="orange", width=300)
        self.commands_frame.pack(side=tkinter.RIGHT)

        self.mainFrame = tkinter.Frame(self, borderwidth=0, width=500)
        # self.mainFrame.config(padx='3.0m', pady='3.0m')
        self.mainFrame.config(padx='0.0m', pady='0.0m')
        self.mainFrame.pack(side=tkinter.LEFT, fill=tkinter.Y)
        # self.mainFrame.grid()
        self.make_header()

        self.gridDict = {}
        for i in range(1, len(self.colList)):
            for j in range(len(self.rowList)):
                w = EntryWidget(self.mainFrame, i, j+1)
                self.gridDict[(i-1,j)] = w.value

                def handler(event, col=i-1, row=j):
                    return self.__entryhandler(col, row)
                w.bind(sequence="<FocusOut>", func=handler)

        for i in range(len(self.colList)+1):
            self.mainFrame.columnconfigure(i,weight=1)
        for i in range(len(self.rowList)+1):
            self.mainFrame.rowconfigure(i,weight=1)

        newt = tkinter.Button(self.mainFrame, text='pita', width=15)
        newt.grid(row=len(self.rowList)+2, column=4, columnspan=3)
        # self.pack()
        self.mainloop()

    def make_header(self):
        self.hdrDict = {}
        for i, label in enumerate(self.colList):
            def handler(event, col=i, row=0, text=label):
                return self.__headerhandler(col, row, text)
            w = LabelWidget(self.mainFrame, i, 0, label)
            self.hdrDict[(i,0)] = w
            w.bind(sequence="<KeyRelease>", func=handler)

        for i, label in enumerate(self.rowList):
            def handler(event, col=0, row=i+1, text=label):
                return self.__headerhandler(col, row, text)
            w = LabelWidget(self.mainFrame, 0, i+1, label)
            self.hdrDict[(0,i+1)] = w
            w.bind(sequence="<KeyRelease>", func=handler)
            # self.grid_rowconfigure(i,pad=0)

    def __entryhandler(self, col, row):
        s = self.gridDict[(col,row)].get()
        if s.upper().strip() == "EXIT":
            self.destroy()
        elif s.upper().strip() == "DEMO":
            self.demo()
        elif s.strip():
            print(s)

    def demo(self):
        ''' enter a number into each Entry field '''
        for i in range(len(self.cols)):
            for j in range(len(self.rowList)):
                self.set(i,j,i+1+j)
                self.update_idletasks()

    def __headerhandler(self, col, row, text):
        ''' has no effect when Entry state=readonly '''
        self.hdrDict[(col,row)].text.set(text)

    def get(self, x, y):
        return self.gridDict[(x,y)].get()

    def set(self, x, y, v):
        self.gridDict[(x,y)].set(v)
        return v

if __name__ == "__main__":
    cols = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    rows = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23']
    app = EntryGrid(cols, rows)
