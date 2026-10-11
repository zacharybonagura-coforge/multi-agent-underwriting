Token cost $0.00 as we are running this locally. Latency is the underwriting span.

| run_id | input tokens | output tokens | cost | latency |
|---|---:|---:|---:|---:|
| ada-lovelace-auto | 1050 | 230 | $0.000350 | 10.10s |
| ada-lovelace-home | 1041 | 232 | $0.000350 | 10.31s |
| katherine-johnson-auto | 1014 | 218 | $0.000335 | 12.24s |
| katherine-johnson-home | 1014 | 215 | $0.000333 | 9.59s |
| margaret-hamilton-life | 1029 | 225 | $0.000343 | 10.14s |
| alan-turing-auto | 1055 | 215 | $0.000340 | 9.81s |
| alan-turing-home | 1036 | 210 | $0.000333 | 9.49s |
| dorothy-vaughan-life | 1031 | 224 | $0.000342 | 10.21s |
| hedy-lamarr-auto | 1043 | 227 | $0.000347 | 10.41s |
| hedy-lamarr-home | 1047 | 250 | $0.000363 | 11.51s |
| grace-hopper-auto | 1009 | 216 | $0.000333 | 10.30s |
| grace-hopper-life | 432 | 103 | $0.000150 | 4.71s |
| john-von-neumann-life | 1079 | 242 | $0.000364 | 11.12s |
| john-von-neumann-home | 1113 | 230 | $0.000361 | 10.79s |
| mary-jackson-auto | 1003 | 214 | $0.000330 | 9.93s |
| mary-jackson-life | 1024 | 238 | $0.000351 | 10.80s |
| claude-shannon-home | 1061 | 234 | $0.000355 | 10.63s |
| claude-shannon-auto | 1110 | 244 | $0.000371 | 11.09s |
| radia-perlman-life | 1029 | 225 | $0.000343 | 10.29s |
| edsger-dijkstra-life | 439 | 111 | $0.000157 | 4.97s |
| barbara-liskov-auto | 1044 | 231 | $0.000350 | 10.44s |
| barbara-liskov-home | 1075 | 240 | $0.000361 | 10.63s |
| leslie-lamport-home | 1079 | 262 | $0.000378 | 11.66s |
| frances-allen-auto | 1040 | 228 | $0.000347 | 10.34s |
| tim-berners-lee-auto | 495 | 156 | $0.000198 | 6.99s |
| vint-cerf-home | 1071 | 238 | $0.000359 | 10.80s |
| bob-kahn-life | 467 | 132 | $0.000176 | 5.85s |
| donald-knuth-auto | 469 | 129 | $0.000175 | 5.72s |
| adele-goldberg-life | 440 | 107 | $0.000154 | 4.80s |
| barbara-liskov-life | 439 | 111 | $0.000157 | 4.94s |
| guido-van-rossum-renters | 440 | 105 | $0.000153 | 4.72s |
| **mean** | **894** | **201** | **$0.000302** | **9.20s** |

27718 input tokens
6242 output tokens
Cost $0.00
Total time is 285 seconds
Mean wait is 9.20s
Slowest case is 12.24s.

This would be more acceptable as an overnight batch. Across the 31 cases in this eval, the mean wait is 9.20s seconds and the slowest case, Katherine Johnson's auto application, takes 12.24s seconds. A full application runs four model calls one after another, and each call waits on the previous message, so the applicant's wait is the sum of those calls. We cannot make this application's agents concurrent, since each depend on the previous. Cases that stop at a broken enrichment record still take about 5 seconds. 

A person submitting a quote would sit on a spinner for 9 to 12 seconds on a normal application, which is slightly long for a real-time decision in the request path. If a user had to, it is not the end of the world, but it is not ideal. The whole set completes in 285 seconds, just under five minutes. An overnight window of eight hours at this speed holds roughly 3,100 applications on one machine. Then in the morning, all uncertain cases are queued for human review in reviews/.

Cost here is not an issue, as running it locally does not cost anything. If we used a larger model, we could decrease the latency of the application, allowing users quicker responses, but it could come at a higher cost.
