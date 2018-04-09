# Open Humans Fibit Integration

This repository is based on [oh-data-source-template](https://github.com/OpenHumans/oh-data-source-template).

## Overview

This repository is a reworked integration between Open Humans and Fitbit. See current status section below for more about the current integration and features/goals for enhancements for this new integration.

## Setup

Please work through SETUP.md for both local environment and Heroku setup instructions.

## Current status

The current fitbit integration is baked into the [data processing repo](https://github.com/OpenHumans/open-humans-data-processing/blob/master/sources/fitbit.py). After a user links Fitbit successfully and starts an import, the main OH site fires off a task to the data processing application which starts a task via celery to fetch & store the data.

Here is a high-level overview of the JSON returned after you connect your fitbit accout to OH and look at your own JSON:

![](https://cl.ly/080z3u2C2f21/Screen%20Shot%202018-02-24%20at%204.52.43%20PM.png)

## Features / Goals

- Break integration into standalone app
    - This app links to OH and Fitbit - need to allow users a way to add their own Client ID & Client Secret from Fitbit if they want Intraday data
- Add Intraday data fetching
- Add workflow for users to create a Personal App (only type that allows Intraday data)
- Allow users to skip intraday (makes setup simpler)
- Create UI that lets user select what granularity of data they want (date range/time intervals) as it's customizable.

## More Info

There is Intraday data available for the following resources (docs linked):

- [Heart](https://dev.fitbit.com/build/reference/web-api/heart-rate/#get-heart-rate-intraday-time-series)
- [Activity](https://dev.fitbit.com/build/reference/web-api/activity/#get-activity-intraday-time-series)

There have been updates to the Sleep API since the current integration was written. Sleep (v1) has an old (deprecated now) endpoint to retrieve time-series data (intraday) from sleep logs, but the new `1.2` API from Fitbit [allows fetching of logs in 30 or 60 second granularity for date ranges](https://dev.fitbit.com/build/reference/web-api/sleep/#get-sleep-logs-by-date-range), without special access.

From some basic exploring, it also appears as though there may be additional information available in payloads that could be evaluated for fetching, as some objects (ex: profile) are currently simplifed by the OH Fitbit importer.

There is a [Swagger playground](https://dev.fitbit.com/build/reference/web-api/explore/#/) available for the APIs.

## Fitbit API caps / rate limiting

The Fitbit API has rate limits which you can [read more about here](https://dev.fitbit.com/build/reference/web-api/basics/#rate-limits).

## User Story / App Flow

This is a potential "user story" for the new integration:

1. User opens app, links to Open Humans via OAuth2
2. User does a standard link to fitbit, like how the process is in the current integration.
3. After the integration is complete, signal to user that all "standard" Fitbit data is downloaded and queued for download on Open Humans to the linked account. 

_Optional workflow after integration is complete for intraday data_

4. Show information to user about intraday data (minute/second level) and that it requires some manual work (to go to the Fitbit site and make a Personal OAuth2 app).
5. If the user chooses to do this, allow them to enter the client ID and secret from Fitbit. Then queue an additional different file(s) for intraday fitbit data upload to Open Humans.

Because the intraday datasets can get large as they are minute/second intervals, we should upload a separate gzipped file to Open Humans.