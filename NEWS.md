Version 1.1.2 (2023.05.27)
----------------------------

* Added speech to transition from ">0 disconnects" to "0 disconnects" to place more perceptible mark on such instant

* Year's passed by...


Version 1.1.0 (2023.03.15)
----------------------------

* Added adjustable delay of alarm speech to suppress speech in case of frequent short disconnections 

* Remapped some switching keys: D for speech delay, H for history mode, I for speech interval

* Renamed "hush" to "interval" to make its purpose clearer

* Added release with binaries for 64-bit Ubuntu and 32/64-bit Windows


Version 1.0.12 (2022.12.26)
----------------------------

* Fixed translation of "unreachable" (node) to parse ping stdout correctly

* Before check, node's history record is cleared from result of previous pass over history ring buffer

* Added horizontal oscillation of title as visual clue that system has not hung


Version 1.0.10 (2022.09.05)
---------------------------

* Parsing of "ping" output handles correctly 2 localisations in addition to English default, and output codepage can be configured in aranealarm.json

* Checkrate can be specified in aranealarm.json

* Added minimum response time to node's statistics

* 128 music volume levels instead of 100

* Rolled back to right corners from round ones because the latter are absent in some console fonts


Version 1.0.8 (2022.06.05)
--------------------------

* Added moving to previous/next disconnected node, to navigate quicker when the entire list of nodes is large enough

* Added "fast" scrolling of the past and jumping to first pass

* More response time statistics: difference, and its sign, between current and previous passes

* Minor alterations


Version 1.0.6 (2022.05.22)
--------------------------

* Added scrolling of log and history to see beyond what fits into one screen

* Added statistics of response time: mean (μ) and standard deviation (σ)

* Added 9 response data slots and 3 types of such data for IP nodes: TTL and derived hops (guess), OS (guess)

* Minor changes


Version 1.0.4 (2022.05.18)
--------------------------

* Hushing does not switch off automatically when the set of disconnected nodes changes, but is toggled only manually and adds non-zero customizable interval between alarm voice messages, which cannot be suppressed completely

* Duration of current quiet/alarm mode is shown

* Tiny interface adjustments and code changes


Version 1.0.2 (2022.05.15)
--------------------------

* Fixed CPU overusage => overheat: added idling to main loops. What a stupid omission...

* Added NEWS


Version 1.0.0 (2022.05.14)
--------------------------

* Initial release