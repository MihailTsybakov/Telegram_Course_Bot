# -*- coding: utf-8 -*-
import pandas as pds
import requests
import time
import datetime
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plot
import bs4 as bs
import telebot

token = '**********'

# Function which returns collected data (now collects USD course):
def getData(latency, observeHours):
    datasetSize = observeHours * 10
    sourceURL = 'https://www.calc.ru/forex-USD-RUB.html'
    queryHeaders = {'User-Agent' : 'Mozilla/5.0 (Linux; Android 5.0; SM-G920A)'+
                    ' AppleWebKit (KHTML, like Gecko) Chrome Mobile Safari'+
                    ' (compatible; AdsBot-Google-Mobile; +http://www.google.com'+
                    '/mobile/adsbot.html)', 'Accept' : 'text/html'}
    dataString = ''
    for _ in range(0, datasetSize):
        # Getting course page:
        coursePage = requests.get(sourceURL, headers = queryHeaders)
        # Creating parse object:
        parsePage = bs.BeautifulSoup(coursePage.text, 'html.parser')
        # Locating usd span and getting value:
        usdCourse = parsePage.find('div', {'class' : 't18'}).text.split(' ')[3]
        dataString += usdCourse + '\n'
        print('Got data: {0}'.format(usdCourse))
        time.sleep(latency)
    dataString = dataString[ : len(dataString) - 1]
    return dataString

# Calculating: growth/reduction, average value, maximum deviation, further forecast 
# Processing data:
def calculateResults(data, latency):
    dataArr = list(map(lambda value: float(value.replace(',', '.')), data.split('\n')))
    dataset = pds.DataFrame({'USD' : dataArr})
    meanValue = round(dataset['USD'].mean(), 4)
    delta = round(dataset['USD'][len(dataset['USD']) - 1] - dataset['USD'][0], 4)
    deviations = []
    for value in dataset['USD']:
        deviations.append(round((value - meanValue), 4))
    # USD course behavior forecast calculates as linear interpolation:
    Phi_0, Phi_x, F = [], [], []
    for index in range(0, len(dataset['USD'])):
        Phi_0.append(1)
        Phi_x.append(index + 1)
        F.append(dataset['USD'][index])
    vectors = [Phi_0, Phi_x, F]
    gramMatrix = []
    for index in range(0, 2):
        tempArr = []
        if (index == 0):
            tempArr.append(sum(list(map(lambda x1, x2: x1 * x2, Phi_0, Phi_0))))
            tempArr.append(sum(list(map(lambda x1, x2: x1 * x2, Phi_0, Phi_x))))
            tempArr.append(sum(list(map(lambda x1, x2: x1 * x2, Phi_0, F))))
            gramMatrix.append(tempArr)
        if (index == 1):
            tempArr.append(sum(list(map(lambda x1, x2: x1 * x2, Phi_x, Phi_0))))
            tempArr.append(sum(list(map(lambda x1, x2: x1 * x2, Phi_x, Phi_x))))
            tempArr.append(sum(list(map(lambda x1, x2: x1 * x2, Phi_x, F))))
            gramMatrix.append(tempArr)
    solveCoef = (-1) * gramMatrix[1][0] / gramMatrix[0][0]
    gramMatrix[1] = list(map(lambda row1Value, row2Value: row2Value + row1Value * solveCoef, gramMatrix[0], gramMatrix[1]))
    # y = kx + b:
    coef_K = gramMatrix[1][2] / gramMatrix[1][1]
    coef_B = (gramMatrix[0][2] - gramMatrix[0][1] * coef_K) / gramMatrix[0][0]
    if (coef_K == 0):
        forecast = 'Neutral: USD course stable'
    if (coef_K > 0):
        forecast = 'Positive forecast: + {0} per {1} minutes'.format('%0.7f'%coef_K, latency/60)
    if (coef_K < 0):
        forecast = 'Negative forecast: {0} per {1} minutes'.format('%0.7f'%coef_K, latency/60)
    # Forming .png plot:
    interX, interY = [], []
    xTicks, yTicks = [], []
    for index in range(1, len(dataset['USD']) + 1):
        interX.append(index)
        interY.append(coef_K * index + coef_B)
    for index in range(0, len(dataset['USD'])):
        if (index % 10 == 0):
            xTicks.append(index)
    for index in range(1, 11):
        yTicks.append(round(meanValue - 0.05 + index * 0.01, 4))
    
    plotColor = 'tan'
    figure = plot.figure(1, facecolor = 'black')
    axis = figure.add_subplot(111, facecolor = 'black')
    axis.set_xlabel('Iteration, {} min'.format(latency/60), color = plotColor)
    axis.set_ylabel('USD, Rubles', color = 'deepskyblue')
    axis.set_xticks(xTicks)
    axis.set_yticks(yTicks)
    axis.set_ylim(min(dataset['USD']) - 0.001, max(dataset['USD']) + 0.001)
    axis.grid(axis = 'both', linewidth = 0.3, color = 'darkgrey')
    axis.plot(dataset.index, dataset['USD'], color = 'deepskyblue', zorder = 1)
    if (coef_K < 0):
        axis.plot(interX, interY, color = 'tomato', linewidth = 0.9, linestyle = '--')
    else:
        axis.plot(interX, interY, color = 'lightgreen', linewidth = 0.9, linestyle = '--')
    axis.spines['bottom'].set_color(plotColor)
    axis.spines['left'].set_color(plotColor)
    axis.tick_params(color = plotColor)
    axis.set_yticklabels(yTicks, color = plotColor, size = 8)
    axis.set_xticklabels(xTicks, color = plotColor, size = 8)
    figure.savefig('Test_Plot', facecolor = 'black')
    plot.close('all')
    return {'mean' : meanValue, 'delta' : delta, 'forecast' : forecast, 'deviations' : deviations, 'firstValue' : dataset['USD'][0]}

# ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ----
# ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ----
currTime = datetime.datetime.now()
timeString = ('<{0}h:{1}m:{2}s>'.format(currTime.hour, currTime.minute, currTime.second))
print(timeString + 'Starting...')

courseBot = telebot.TeleBot(token)
@courseBot.message_handler(content_types = ['text'])
def start_handle(message):
    if (message.text == '/start'):
        courseBot.send_message(message.chat.id, 'Welcome. I`m a FinBot, I will help you to gather some info about USD course.')
        courseBot.send_message(message.chat.id, 'To start new analysis, enter number of observation hours, for example: "3". ' +
                               'I`ll look for USD course every 6 minutes and then I`ll send you some info about USD dynamics. ' +
                               'Lets get it started.')
    satisfyFlag = 0
    try:
        observeTime = int(message.text)
        satisfyFlag = 1
    except ValueError:
        satisfyFlag = 0
    if (message.text != '/start' and satisfyFlag == 0):
        courseBot.send_message(message.chat.id, 'Sorry, I cant understand you. Try again.')
    if (satisfyFlag == 1):
        currTime = datetime.datetime.now()
        timeString = ('<{0}h:{1}m:{2}s>'.format(currTime.hour, currTime.minute, currTime.second))
        print(timeString + 'Got properties: {0}'.format(observeTime))
        weekDay = datetime.datetime.today().weekday()
        if (observeTime >= 4):
            courseBot.send_message(message.chat.id, 'Sorry, we dont support such large properties yet. Try lower values.')
        elif (observeTime <= 0):
            courseBot.send_message(message.chat.id, 'Ivalid properties. Try another values.')
        else:
            endHour, endMinute = str((currTime.hour + observeTime) % 24), str(currTime.minute)
            if (len(endHour) == 1):
                endHour = '0' + endHour
            if (len(endMinute) == 1):
                endMinute = '0' + endMinute
            courseBot.send_message(message.chat.id, 'I got it. Results will arrive ~ at {0}:{1}'.format(endHour, endMinute))
            if (weekDay == 5 or weekDay == 6):
                courseBot.send_message(message.chat.id, 'Warning: It`s weekend day, result may be not relevant.')            
            dataString = getData(360, observeTime)
            results = calculateResults(dataString, 360)
            courseBot.send_message(message.chat.id, 'Done. Lets consider results.')
            if (weekDay == 5 or weekDay == 6):
                if (results['delta'] == 0):
                    courseBot.send_message(message.chat.id, 'It`s weekend, no USD activity detected')
            time.sleep(2)
            courseBot.send_message(message.chat.id, '> During that observation period, mean USD value is {} Rub'.format(results['mean']))
            courseBot.send_message(message.chat.id, '> USD behavior forecast: {}\n\n(Hint: forecast is most relevant for long-term observation)'.format(results['forecast']))
            deviations = results['deviations']
            maxDev, minDev = '-','-'
            if (max(deviations) > 0):
                maxDev = '> Max "+" deviation is {0} ({1} % of mean value)'.format(max(deviations), round((abs(max(deviations))/results['mean'])*100, 4))
            if (min(deviations) < 0):
                maxDev = '> Max "-" deviation is {0} ({1} % of mean value)'.format(min(deviations), round((abs(min(deviations))/results['mean'])*100, 4))
            delta = results['delta']
            if (maxDev != '-'):
                courseBot.send_message(message.chat.id, maxDev)
            if (minDev != '-'):
                courseBot.send_message(message.chat.id, minDev)
            courseBot.send_message(message.chat.id, '> Growth / Reduction: {0} ({1} % of first value)'.format(delta, round(delta/results['firstValue']*100, 4)))
            courseBot.send_message(message.chat.id, '> Some graphics:')
            USDgraphic = open('Test_Plot.png', 'rb')
            courseBot.send_photo(message.chat.id, USDgraphic)
            courseBot.send_message(message.chat.id, 'Thats all for now.')        

if __name__ == '__main__':
    courseBot.polling()
    
currTime = datetime.datetime.now()
timeString = ('<{0}h:{1}m:{2}s>'.format(currTime.hour, currTime.minute, currTime.second))
print(timeString + 'Shutting down...')

    
    
    
