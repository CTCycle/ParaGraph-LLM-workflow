export type HistoryEntry<T> = {
    before: T
    after: T
    kind: 'mutate' | 'move'
    timestamp: number
}

export class CommandHistory<T> {
    private undoStack: HistoryEntry<T>[] = []
    private redoStack: HistoryEntry<T>[] = []

    record(entry: HistoryEntry<T>): void {
        const previous = this.undoStack[this.undoStack.length - 1]
        const canCoalesce =
            previous &&
            previous.kind === 'move' &&
            entry.kind === 'move' &&
            entry.timestamp - previous.timestamp < 120

        if (canCoalesce) {
            this.undoStack[this.undoStack.length - 1] = {
                ...previous,
                after: entry.after,
                timestamp: entry.timestamp,
            }
        } else {
            this.undoStack.push(entry)
        }

        this.redoStack = []
    }

    undo(current: T): T {
        const entry = this.undoStack.pop()
        if (!entry) {
            return current
        }
        this.redoStack.push({
            before: entry.after,
            after: entry.before,
            kind: entry.kind,
            timestamp: Date.now(),
        })
        return entry.before
    }

    redo(current: T): T {
        const entry = this.redoStack.pop()
        if (!entry) {
            return current
        }
        this.undoStack.push({
            before: entry.after,
            after: entry.before,
            kind: entry.kind,
            timestamp: Date.now(),
        })
        return entry.before
    }

    clear(): void {
        this.undoStack = []
        this.redoStack = []
    }
}