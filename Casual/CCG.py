import asyncio
import PySimpleGUI as sg
from datetime import datetime, date

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from playwright.async_api import async_playwright, expect


def make_win1():
    addreses = ["https://www.cinema-city.pl/kina/kinepolis/1081#/",
                "https://www.cinema-city.pl/kina/poznanplaza/1078#/",
                "https://www.cinema-city.pl/kina/wroclavia/1097#/",
                "https://www.cinema-city.pl/kina/korona/1067#/",
                "https://www.cinema-city.pl/kina/mokotow/1070#/"
                ]

    layout_main = [
        [sg.Text("Address")],
        [sg.Combo(addreses, size=(50, 1), default_value=addreses[0], key="address")],
        [sg.Input(size=(30, 1), default_text=str(date.today()), key="date"),
         sg.CalendarButton("Pick date", format="%Y-%m-%d", size=(11, 1), key="calendar")],
        [sg.Button("Ok", disabled=False, key="ok")],
    ]
    return sg.Window("Cinema Grabber", layout_main, element_justification='center', finalize=True)


def main():
    sg.theme("DarkAmber")

    window1, window2 = make_win1(), None

    tabs_no = 0

    while True:
        window, event, values = sg.read_all_windows()
        if event == sg.WIN_CLOSED and window == window1:
            break
        if event == sg.WIN_CLOSED and window == window2:
            window2.close()
        if event == 'calendar':
            screenings_date = sg.popup_get_date()
            if screenings_date:
                month, day, year = screenings_date
                window['date'].update(f"{year}-{month:0>2d}-{day:0>2d}")
        if event == "ok":
            day = datetime.strptime(values["date"], "%Y-%m-%d").date()
            address = values["address"] + "?at={}".format(day)
            print("You entered ", day)

            column1 = []
            fetch_result = window1.perform_long_operation(lambda: asyncio.run(fetch(address, column1)), "-END KEY-")

            window1["ok"].update(disabled=True)
        if event == "-END KEY-":
            # todo more windows per launch
            # window1["ok"].update(disabled=False)

            movies_fetched = values[event]

            tab_group = [
                [sg.Tab("Graph", [[sg.Canvas(key='-CANVAS-')]]),
                 sg.Tab("List", [[
                     sg.Button("-PRINT-"),
                     sg.Column(column1, scrollable=True, vertical_scroll_only=True, size=(2000, 2000))
                     ]]),
                 ],
            ]
            layout_screenings = [
                [sg.TabGroup(tab_group, enable_events=True, key='-TABGROUP-')],
            ]

            window2 = sg.Window("Screenings", layout_screenings, size=(1200, 600), finalize=True,
                                element_justification='center')
            draw_figure(window2['-CANVAS-'].TKCanvas, make_plot(movies_fetched))

            window2.reappear()

        if event == "-PRINT-":
            justChecked = [element[1] for element in values if values[element] == True and 'TITLE' in element]

            window2['-TABGROUP-'].add_tab(sg.Tab("Graph", [[sg.Canvas(key=('-CANVAS2-', tabs_no))]]))
            draw_figure(window2[('-CANVAS2-', tabs_no)].TKCanvas, make_plot(movies_fetched, justChecked))

            tabs_no += 1

    window1.close()


def draw_figure(canvas, figure):
    figure_canvas_agg = FigureCanvasTkAgg(figure, canvas)
    figure_canvas_agg.draw()
    figure_canvas_agg.get_tk_widget().pack(side='top', fill='both', expand=1)


def make_plot(movies, chosen=None):
    titles = []
    xs = []
    ys = []
    scr_cnt = 0

    if chosen is None:
        for movie in movies:
            for screen in movie.screenings:
                titles.append("{} {} {}".format(movie.title, screen.movie_type, screen.movie_lang))
                xs.append(list(map(lambda x: float(norm_hours(x.replace(":", "."))), screen.start_hours)))
                ys.append(list(map(lambda x: float(norm_hours(x.replace(":", "."))), screen.end_hours)))
    else:
        scr_cnt = 0
        for n in chosen:
            for screen in movies[n].screenings:
                titles.append("{} {} {}".format(movies[n].title, screen.movie_type, screen.movie_lang))
                xs.append(list(map(lambda x: float(norm_hours(x.replace(":", "."))), screen.start_hours)))
                ys.append(list(map(lambda x: float(norm_hours(x.replace(":", "."))), screen.end_hours)))
                scr_cnt += 1

    with plt.rc_context({'ytick.color': sg.rgb(213, 112, 49),
                         'xtick.color': sg.rgb(213, 112, 49),
                         'axes.facecolor': sg.rgb(54, 53, 55),
                         'figure.facecolor': sg.rgb(31, 30, 31)}):
        fig = plt.figure(figsize=(16, 10), dpi=100)
        ax = plt.axes()

    plt.subplots_adjust(left=0.20, right=0.99, top=0.99, bottom=0.05)

    for n in range(len(xs)):
        for i in range(len(xs[n])):
            x1, x2 = xs[n][i], ys[n][i]
            y1, y2 = n, n
            plt.plot([x1, x2], [y1, y2], '-|', color=sg.rgb(213, 112, 49))

    plt.xticks(range(10, 25))
    plt.yticks(range(len(xs)), titles, wrap=True, fontsize=8)
    plt.grid(color=sg.rgb(31, 30, 31))

    if chosen is not None:
        if 1 < scr_cnt < 10:
            ax.set_ylim(-1, scr_cnt)

    return fig


# simple time addition
def add_mins(hour, duration):
    t_hour, t_mins = hour.split(":")
    t_hour = int(t_hour)
    t_mins = int(t_mins)

    hours = duration // 60
    mins = duration % 60

    if t_mins + mins >= 60:
        t_hour += 1
        t_mins = t_mins + mins - 60
    else:
        t_mins += mins

    t_hour += hours

    if t_mins >= 10:
        return "{}:{}".format(t_hour, t_mins)
    else:
        return "{}:0{}".format(t_hour, t_mins)


def norm_hours(hour):

    hour2 = hour.split(".")

    hour2[1] = round(np.interp([int(hour2[1])], [0, 60], [0, 100])[0])
    if hour2[1] < 10:
        hour2[1] = "0" + str(hour2[1])
    else:
        hour2[1] = str(hour2[1])

    hour2 = ".".join(hour2)

    return hour2


class Movie:
    def __init__(self, title, duration, screenings):
        self.title = title
        self.duration = duration
        self.screenings = screenings


class Screening:
    def __init__(self, movie_type, movie_lang, start_hours, end_hours):
        self.movie_type = movie_type
        self.movie_lang = movie_lang
        self.start_hours = start_hours
        self.end_hours = end_hours


async def fetch(address, layout):
    # create movies array, initialize playwright
    movies = []
    movie_num = 0
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page()
        await page.goto(address)

        # fetch all movies
        await expect(page.locator(".qb-movie-details")).not_to_have_count(0)
        all_items = await page.query_selector_all(".qb-movie-details")

        # for each movie fetch title, duration, and all screening types
        for item in all_items:
            tmp_screenings = []
            title = await (await item.query_selector(".qb-movie-name")).inner_text()

            details = await item.query_selector(".qb-movie-info")
            duration = int((await details.inner_text()).split("|")[1].split(" ")[0])

            screenings = await item.query_selector_all(".qb-movie-info-column")
            isnt_played = False

            # for all screening types get their type, language and hours
            for screening in screenings:
                # if a movie is not played that day ignore it
                if movie_type := await screening.query_selector(".qb-screening-attributes"):
                    movie_type = await movie_type.inner_text()
                else:
                    isnt_played = True
                    continue

                movie_lang = (await (await screening.query_selector(".qb-movie-attributes")).inner_text()).replace("·",
                                                                                                                   " ")
                hours_temp = await screening.query_selector_all("a")

                # for each screening calculate what time it ends
                start_hours = []
                end_hours = []
                for hour in hours_temp:
                    tmp_hour = await hour.inner_text()
                    start_hours.append(tmp_hour)
                    end_hours.append(add_mins(tmp_hour, duration))

                tmp_screenings.append(Screening(movie_type, movie_lang, start_hours, end_hours))

            if isnt_played:
                continue

            tmp_movie = Movie(title, duration, tmp_screenings)

            movies.append(tmp_movie)

            layout.append([sg.Checkbox("{}".format(tmp_movie.title), key=("TITLE", movie_num)), sg.Text("{}min".format(tmp_movie.duration))])

            for screening in tmp_movie.screenings:
                layout.append([sg.Text("\t{} {}".format(screening.movie_type, screening.movie_lang))])
                layout.append([sg.Text("\t\tStarting hours:\t"), sg.Text(screening.start_hours)])
                layout.append([sg.Text("\t\tEnding hours:\t"), sg.Text(screening.end_hours)])
            layout.append([sg.Text("")])

            movie_num += 1

        await browser.close()

        return movies


if __name__ == '__main__':
    main()
