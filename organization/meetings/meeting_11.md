# Meeting — 2026-07-06

**Moderator:** [Andreas]\
**Note-taker:** [Adrian]\
**Attendees:** [Andreas, Adrian, Nils, Waleed, Lucas]

## Agenda
1. Progress report
2. Final week planning

## Discussion
* **Inference**
    * test Octo inference with new finetuned model using new large data set
    * incorporate unnormalization statistics to avoid going over joint limits
    * more data needed to avoid overfitting?
    * integrate inference pipeline
    * if inference does not work: show zero-shot benchmarks and analyze why finetuned model is worse or same as zero-shot

* **Poster**
    * scientific-style poster detailing the project
    * no spelling/grammar mistakes
    * two versions: normal poster and one marked version
        * mark who made which part of the poster
        * contribution to implementation is secondary
    * unified design
    * mix of text and images but more text than in a presentation is allowed
    
* **Unfinished Features**
    * put unfinished code into unimplemented/deprecated folder/branch
    * adhere to a time plan and make sure tasks are completed 

## Decisions
* **Final Week Focus**: prioritize inference testing and analysis over finishing auxiliary features

## Action Items
| Task | Owner | Deadline |
|------|-------|----------|
| Refactoring & cleanup | Everyone | 2026-07-12 |
| Create & hand in poster | Everyone | 2026-07-12 |
| Finalize & hand in test plan | Adrian & Johannes | 2026-07-12 |
| Finalize & hand in project specification | Waleed | 2026-07-12 |
| Fix episode replay | Adrian | 2026-07-12 |
| Add Svelte compiling and linting to CI/CD | Andreas & Elkholy | 2026-07-12 |
| Split inference code into back-end | Elkholy | 2026-07-12 |

## Next Meeting
- **Date:** N/A
- **Moderator:** N/A
- **Note-taker:** N/A
