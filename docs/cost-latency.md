Token cost is $0.00, as this batch was run locally. Latency is the underwriting span.

| run_id | input tokens | output tokens | cost | latency |
|---|---:|---:|---:|---:|
| ada-lovelace-auto | 995 | 205 | $0.000323 | 12.94s |
| ada-lovelace-home | 986 | 207 | $0.000322 | 13.40s |
| katherine-johnson-auto | 953 | 191 | $0.000305 | 12.62s |
| katherine-johnson-home | 953 | 188 | $0.000303 | 12.45s |
| margaret-hamilton-life | 970 | 199 | $0.000314 | 13.54s |
| alan-turing-auto | 995 | 188 | $0.000311 | 12.82s |
| alan-turing-home | 976 | 183 | $0.000304 | 12.76s |
| dorothy-vaughan-life | 960 | 192 | $0.000307 | 13.34s |
| hedy-lamarr-auto | 975 | 196 | $0.000313 | 13.82s |
| hedy-lamarr-home | 995 | 227 | $0.000338 | 15.97s |
| grace-hopper-auto | 953 | 191 | $0.000305 | 12.84s |
| grace-hopper-life | 381 | 78 | $0.000123 | 5.52s |
| john-von-neumann-life | 1028 | 219 | $0.000338 | 15.24s |
| john-von-neumann-home | 1062 | 207 | $0.000336 | 14.21s |
| mary-jackson-auto | 948 | 189 | $0.000303 | 14.27s |
| mary-jackson-life | 981 | 219 | $0.000330 | 14.85s |
| claude-shannon-home | 1001 | 207 | $0.000325 | 13.88s |
| claude-shannon-auto | 1050 | 217 | $0.000341 | 14.54s |
| radia-perlman-life | 967 | 197 | $0.000312 | 12.80s |
| edsger-dijkstra-life | 378 | 77 | $0.000122 | 5.03s |
| barbara-liskov-auto | 977 | 196 | $0.000313 | 13.23s |
| barbara-liskov-home | 1008 | 209 | $0.000328 | 13.93s |
| leslie-lamport-home | 1007 | 229 | $0.000342 | 15.54s |
| frances-allen-auto | 968 | 195 | $0.000311 | 13.82s |
| tim-berners-lee-auto | 428 | 125 | $0.000165 | 8.73s |
| vint-cerf-home | 1001 | 206 | $0.000324 | 14.68s |
| bob-kahn-life | 399 | 101 | $0.000143 | 6.96s |
| donald-knuth-auto | 402 | 99 | $0.000142 | 6.79s |
| adele-goldberg-life | 373 | 94 | $0.000133 | 6.41s |
| barbara-liskov-life | 376 | 76 | $0.000121 | 5.22s |
| guido-van-rossum-renters | 375 | 73 | $0.000119 | 5.22s |
| **mean** | **833** | **174** | **$0.000271** | **11.85s** |

25821 input tokens
5380 output tokens
Cost $0.00
Total time is 367 seconds
Mean wait is 11.85s
Slowest case is 15.97s

This would be more acceptable as an overnight batch. Across the 31 cases in this eval, the mean wait is 11.85 seconds and the slowest case, Hedy Lamarr's home application, takes 15.97 seconds. A full application runs four model calls one after another, and each call waits on the previous message, so the applicant's wait is the sum of those calls. We cannot make this application's agents concurrent, since each depend on the previous. Cases that stop at a broken enrichment record still take about 5 seconds. 

A person submitting a quote would sit on a spinner for 12 to 16 seconds on a normal application, which is quite long for a real-time decision in the request path. If a user had to, it is not the end of the world, but it is not ideal. The whole set completes in 367 seconds, about six minutes. An overnight window of eight hours at this speed holds roughly 2,400 applications on one machine. Then in the morning, all uncertain cases are queued for human review in reviews/.

Cost here is not an issue, as running it locally does not cost anything. If we used a larger model, we could decrease the latency of the application, allowing users quicker responses, but it could come at a higher cost.
