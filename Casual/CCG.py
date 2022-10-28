import asyncio
import PySimpleGUI as sg
from datetime import datetime, date

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import playwright
from playwright.async_api import async_playwright, expect


def main():
    sg.theme("DarkAmber")

    layout_main = [
        [sg.Text("Address")],
        [sg.Input(size=(50, 1), default_text="https://www.cinema-city.pl/kina/kinepolis/1081#/", key="address")],
        [sg.Input(size=(30, 1), default_text=str(date.today()), key="date"),
         sg.CalendarButton("Pick date", format="%Y-%m-%d", size=(11, 1), key="calendar")],
        [sg.Button("Ok", disabled=False, key="ok")],
    ]

    window1 = sg.Window("Cinema Grabber", layout_main, element_justification='center')

    while True:
        event, values = window1.read()
        if event == sg.WIN_CLOSED:
            break
        if event == "ok":
            day = datetime.strptime(values["date"], "%Y-%m-%d").date()
            address = values["address"] + "?at={}".format(day)
            print("You entered ", day)

            column1 = []
            fetch_result = window1.perform_long_operation(lambda: asyncio.run(fetch(address, column1)), "-END KEY-")

            window1["ok"].update(disabled=True)
        if event == "-END KEY-":
            window1["ok"].update(disabled=False)

            tab_group = [
                [sg.Tab("Graph", [[sg.Canvas(key='-CANVAS-')]]),
                 sg.Tab("List", [[sg.Column(column1, scrollable=True, vertical_scroll_only=True, size=(2000, 2000))]]),
                 ],
            ]
            layout_screenings = [
                [sg.TabGroup(tab_group, enable_events=True, key='-TABGROUP-')],
            ]

            window2 = sg.Window("Screenings", layout_screenings, size=(1200, 600), finalize=True,
                                element_justification='center')
            fig_canvas_agg = draw_figure(window2['-CANVAS-'].TKCanvas, make_plot(values[event]))

            window2.reappear()

    window1.close()


def draw_figure(canvas, figure):
    figure_canvas_agg = FigureCanvasTkAgg(figure, canvas)
    figure_canvas_agg.draw()
    figure_canvas_agg.get_tk_widget().pack(side='top', fill='both', expand=1)
    return figure_canvas_agg


def make_plot(movies):
    titles = []
    xs = []
    ys = []
    for movie in movies:
        for screen in movie.screenings:
            titles.append("{} {} {}".format(movie.title, screen.movie_type, screen.movie_lang))
            xs.append(list(map(lambda x: float(x.replace(":", ".")), screen.start_hours)))
            ys.append(list(map(lambda x: float(x.replace(":", ".")), screen.end_hours)))

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
    fig.tight_layout()

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

            layout.append([sg.Text("{} {}min".format(tmp_movie.title, tmp_movie.duration))])

            for screening in tmp_movie.screenings:
                layout.append([sg.Text("\t{} {}".format(screening.movie_type, screening.movie_lang))])
                layout.append([sg.Text("\t\tStarting hours:\t"), sg.Text(screening.start_hours)])
                layout.append([sg.Text("\t\tEnding hours:\t"), sg.Text(screening.end_hours)])
            layout.append([sg.Text("")])

        await browser.close()

        return movies


if __name__ == '__main__':
    main()
