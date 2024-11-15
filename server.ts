import express from 'express';
import axios from 'axios';
import mysql from 'mysql2';
import mysqlPromise from 'mysql2/promise';
import cors from 'cors';
import { RowDataPacket, ResultSetHeader } from 'mysql2';

const app = express();
const port = 5001;

// Create a MySQL connection pool
const pool = mysql.createPool({
    host: 'localhost',
    user: 'root',
    password: 'yourpassword',
    database: 'fyp_pc'
});

// Create a promise-based connection pool (mysql2/promise) for async routes
const poolPromise = mysqlPromise.createPool({
    host: 'localhost',
    user: 'root',
    password: 'yourpassword',
    database: 'fyp_pc'
});

// Middleware to handle JSON requests
app.use(express.json());
app.use(cors());

// Route to fetch DBLP data from the Python microservice
app.get('/api/dblp-data', async (req, res) => {
    const { dblpUrl } = req.query;

    if (!dblpUrl) {
        return res.status(400).json({ error: 'Missing dblpUrl parameter' });
    }

    try {
        const response = await axios.get(`http://127.0.0.1:8000/dblp/${dblpUrl}`);
        res.json(response.data);
    } catch (error) {
        console.error("Error fetching DBLP data:", error);
        res.status(500).json({ error: 'Error fetching DBLP data' });
    }
});

// Route to run an iteration
app.post('/api/run_iteration', (req, res) => {
    const { pcSize } = req.body;

    pool.query('SELECT MAX(ITERATION) as maxIteration FROM Candidate_Rec', (err, results: RowDataPacket[]) => {
        if (err) {
            return res.status(500).json({ error: err.message });
        }

        const currentMaxIteration = results[0].maxIteration === null ? 0 : results[0].maxIteration;
        const nextIteration = currentMaxIteration + 1;

        const query = 'SELECT ID, NAME, DECISION, coauthors FROM Candidate_Rec WHERE DECISION IS NULL OR DECISION != "Declined"';

        pool.query(query, (err, candidates: RowDataPacket[]) => {
            if (err) {
                return res.status(500).json({ error: err.message });
            }

            const candidateGraph: { [key: string]: Set<string> } = {};
            const candidateByName: { [key: string]: RowDataPacket } = {};

            const validCandidateNames = new Set(candidates.map(c => c.NAME.toLowerCase()));

            // Build the graph
            candidates.forEach(candidate => {
                const candidateName = candidate.NAME.toLowerCase();
                candidateGraph[candidateName] = candidateGraph[candidateName] || new Set();
                candidateByName[candidateName] = candidate;

                // Get all coathors for candidate
                let coauthors: string[] = [];
                if (candidate.coauthors) {
                    coauthors = Array.isArray(candidate.coauthors)
                        ? candidate.coauthors
                        : JSON.parse(candidate.coauthors || '[]');
                }

                // Get all connections between all candidates
                coauthors.forEach(coauthor => {
                    const coauthorName = coauthor.toLowerCase();
                    // Ensure co-author is a candidate
                    if (validCandidateNames.has(coauthorName) && coauthorName !== candidateName) {
                        // Exclude self-connections
                        if (candidateName !== coauthorName) {
                            candidateGraph[candidateName].add(coauthorName);
                            candidateGraph[coauthorName] = candidateGraph[coauthorName] || new Set();
                            candidateGraph[coauthorName].add(candidateName);
                        }
                    }
                });
            });

            // Get accepted candidates
            const acceptedCandidates = candidates
                .filter(candidate => candidate.DECISION === 'Accepted')
                .map(candidate => candidate.NAME.toLowerCase());

            const selectedCandidates = new Set<string>(acceptedCandidates);

            // No accepted candidates
            if (selectedCandidates.size === 0) {
                // Select least connected candidates directly
                const candidateConnections = Object.keys(candidateGraph).map(candidateName => ({
                    name: candidateName,
                    connections: Array.from(candidateGraph[candidateName]).length,
                }));

                candidateConnections.sort((a, b) => a.connections - b.connections);

                const leastConnectedCandidates = candidateConnections.slice(0, pcSize);
                leastConnectedCandidates.forEach(c => selectedCandidates.add(c.name));
                // There are accepted candidates
            } else {
                // Use greedy algorithm to add minimally connected candidates
                while (selectedCandidates.size < pcSize) {
                    const remainingCandidates = Object.keys(candidateGraph).filter(
                        name => !selectedCandidates.has(name)
                    );

                    const nextCandidate = remainingCandidates.reduce((bestCandidate, candidate) => {
                        const connections = Array.from(candidateGraph[candidate]).filter(
                            coauthor => selectedCandidates.has(coauthor)
                        ).length;

                        if (
                            !bestCandidate ||
                            connections < bestCandidate.connections
                        ) {
                            return { name: candidate, connections };
                        }
                        return bestCandidate;
                    }, null as { name: string; connections: number } | null);

                    if (!nextCandidate) break; // No more candidates to add
                    selectedCandidates.add(nextCandidate.name);
                }
            }

            const selectedCandidateNames = Array.from(selectedCandidates);

            // Update database for selected candidates
            const updateIsSelectedQuery = `
                UPDATE Candidate_Rec
                SET isSelected = TRUE
                WHERE NAME IN (${selectedCandidateNames.map(() => '?').join(', ')})
            `;

            const updateIterationQuery = `
                UPDATE Candidate_Rec
                SET ITERATION = ?
                WHERE DECISION IS NULL OR DECISION = ''
            `;

            pool.query(updateIsSelectedQuery, selectedCandidateNames, (err) => {
                if (err) {
                    return res.status(500).json({ error: err.message });
                }

                pool.query(updateIterationQuery, [nextIteration], (err) => {
                    if (err) {
                        return res.status(500).json({ error: err.message });
                    }

                    res.status(200).json({
                        message: `Selected least connected graph with ${pcSize} candidates.`,
                        selectedCandidates: selectedCandidateNames,
                    });
                });
            });
        });
    });
});



app.get('/api/candidate-network', (req, res) => {
    // Query to get all candidates with isSelected = TRUE
    const query = `
        SELECT ID, NAME, coauthors 
        FROM Candidate_Rec 
        WHERE isSelected = TRUE
    `;

    pool.query(query, (err, candidates: { ID: number; NAME: string; coauthors: string | string[] }[]) => {
        if (err) {
            return res.status(500).json({ error: err.message });
        }

        // Build graph structure
        const nodes: { id: string }[] = []; // Array of nodes for the graph
        const links: { source: string; target: string }[] = []; // Array of links (edges) for the graph
        const candidateMap: { [key: string]: boolean } = {}; // Map to check if a name is a selected candidate

        // Initialize nodes and map for quick lookup
        candidates.forEach((candidate: { ID: number; NAME: string; coauthors: string | string[] }) => {
            const candidateName = candidate.NAME.toLowerCase();
            nodes.push({ id: candidateName });
            candidateMap[candidateName] = true;
        });

        // Build connections (links) based on coauthors who are also selected candidates
        candidates.forEach((candidate: { NAME: string; coauthors: string | string[] }) => {
            const candidateName = candidate.NAME.toLowerCase();
            let coauthors: string[] = [];

            // Parse coauthors if available
            if (candidate.coauthors) {
                coauthors = typeof candidate.coauthors === 'string'
                    ? JSON.parse(candidate.coauthors)
                    : candidate.coauthors;
            }

            // Add links only for coauthors who are also selected candidates
            coauthors.forEach((coauthor: string) => {
                const coauthorName = coauthor.toLowerCase();
                if (candidateMap[coauthorName] && coauthorName !== candidateName) {
                    links.push({ source: candidateName, target: coauthorName });
                }
            });
        });

        // Return the graph data
        res.status(200).json({
            nodes,
            links
        });
    });
});

// Async route example using the promise-based pool
app.put('/api/candidates/batch-selection', async (req, res) => {
    const selections: { userId: string; isSelected: boolean }[] = req.body;

    try {
        const updates = selections.map(({ userId, isSelected }) =>
            poolPromise.query('UPDATE Candidate_Rec SET isSelected = ? WHERE ID = ?', [isSelected, userId])
        );

        // Use Promise.all to wait for all updates to complete
        await Promise.all(updates);

        res.status(200).json({ message: 'Batch update successful' });
    } catch (error) {
        res.status(500).json({ error });
    }
});

// app.get('/api/least-connected-candidates', (req, res) => {
//     // Select the candidates with their coauthors
//     const query = 'SELECT ID, NAME, EMAIL, INSTITUTE, COUNTRY, coauthors FROM Candidate_Rec';

//     pool.query(query, (err, results: RowDataPacket[]) => {
//         if (err) {
//             return res.status(500).json({ error: err.message });
//         }

//         const candidatesWithConnections = results.map(candidate => {
//             console.log(candidate);
//             let coauthors: string[] = [];
//             if (candidate.coauthors === null || candidate.coauthors === undefined) {
//                 coauthors = [];
//             } else if (Array.isArray(candidate.coauthors)) {
//                 coauthors = candidate.coauthors;
//             } else if (typeof candidate.coauthors === 'string') {
//                 try {
//                     coauthors = JSON.parse(candidate.coauthors);
//                 } catch (error) {
//                     console.error(`Error parsing coauthors for candidate ID: ${candidate.ID}`, error);
//                     coauthors = [];
//                 }
//             }
//             return {
//                 ...candidate,
//                 connectionCount: coauthors.length
//             };
//         });

//         // Sort candidates by connection count (ascending) and return the top 10
//         const leastConnectedCandidates = candidatesWithConnections
//             .sort((a, b) => a.connectionCount - b.connectionCount)
//             .slice(0, 10);

//         res.status(200).json(leastConnectedCandidates);
//     });
// });

// Route to get data from Candidate_Rec table
app.get('/api/candidates', (req, res) => {
    pool.query('SELECT * FROM Candidate_Rec', (err, results) => {
        if (err) {
            return res.status(500).json({ error: err.message });
        }
        res.json(results);
    });
});

app.post('/api/candidates', (req, res) => {
    const {
        NAME,
        EMAIL,
        INSTITUTE,
        COUNTRY,
        COUNTRYOFORIGIN,
        GENDER,
        LEVEL,
        EXPERTISE,
        DBLP,
        ITERATION,
        DECISION,
        coauthor_hist,
        years_of_pub,
        coauthors
    } = req.body;

    const query = `
        INSERT INTO Candidate_Rec 
        (NAME, EMAIL, INSTITUTE, COUNTRY, COUNTRYOFORIGIN, GENDER, LEVEL, EXPERTISE, DBLP, ITERATION, DECISION, coauthor_hist, years_of_pub, coauthors) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `;

    pool.query(
        query,
        [NAME === '' ? null : NAME,
        EMAIL === '' ? null : EMAIL,
        INSTITUTE === '' ? null : INSTITUTE,
        COUNTRY === '' ? null : COUNTRY,
        COUNTRYOFORIGIN === '' ? null : COUNTRYOFORIGIN,
        GENDER === '' ? null : GENDER,
        LEVEL === '' ? null : LEVEL,
        EXPERTISE === '' ? null : EXPERTISE,
        DBLP === '' ? null : DBLP,
        ITERATION === '' ? null : ITERATION,
        DECISION === '' ? null : DECISION,
        coauthor_hist === '' ? null : JSON.stringify(coauthor_hist),
        years_of_pub === '' ? null : JSON.stringify(years_of_pub),
        coauthors === '' ? null : JSON.stringify(coauthors),
        ],
        (err) => {
            if (err) {
                return res.status(500).json({ error: err.message });
            }
            console.log("Query Results:", req.body);
            res.status(201).json(req.body);
        }
    );
});

app.put('/api/candidates/:id', (req, res) => {
    const { id } = req.params;
    const {
        NAME,
        EMAIL,
        INSTITUTE,
        COUNTRY,
        COUNTRYOFORIGIN,
        GENDER,
        LEVEL,
        EXPERTISE,
        DBLP,
        ITERATION,
        DECISION
        // coauthor_hist, years_of_pub, coauthors are excluded
    } = req.body;

    const selectQuery = 'SELECT * FROM Candidate_Rec WHERE ID = ?';

    pool.query(selectQuery, [id], (err, results: RowDataPacket[]) => {
        if (err) {
            return res.status(500).json({ error: err.message });
        }

        const existingCandidate = results[0];
        if (!existingCandidate) {
            return res.status(404).json({ error: 'Candidate not found' });
        }

        // Merge incoming data with existing data
        const updatedCandidate = {
            NAME: NAME || existingCandidate.NAME,
            EMAIL: EMAIL || existingCandidate.EMAIL,
            INSTITUTE: INSTITUTE || existingCandidate.INSTITUTE,
            COUNTRY: COUNTRY || existingCandidate.COUNTRY,
            COUNTRYOFORIGIN: COUNTRYOFORIGIN || existingCandidate.COUNTRYOFORIGIN,
            GENDER: GENDER || existingCandidate.GENDER,
            LEVEL: LEVEL || existingCandidate.LEVEL,
            EXPERTISE: EXPERTISE || existingCandidate.EXPERTISE,
            DBLP: DBLP || existingCandidate.DBLP,
            ITERATION: ITERATION || existingCandidate.ITERATION,
            DECISION: DECISION || existingCandidate.DECISION,
            // coauthor_hist, years_of_pub, and coauthors are kept intact
            coauthor_hist: existingCandidate.coauthor_hist,
            years_of_pub: existingCandidate.years_of_pub,
            coauthors: existingCandidate.coauthors
        };

        // Update only the allowed fields
        const updateQuery = `
            UPDATE Candidate_Rec
            SET NAME = ?, EMAIL = ?, INSTITUTE = ?, COUNTRY = ?, COUNTRYOFORIGIN = ?, GENDER = ?, LEVEL = ?, EXPERTISE = ?, DBLP = ?, ITERATION = ?, DECISION = ?
            WHERE ID = ?
        `;

        pool.query(
            updateQuery,
            [
                updatedCandidate.NAME,
                updatedCandidate.EMAIL,
                updatedCandidate.INSTITUTE,
                updatedCandidate.COUNTRY,
                updatedCandidate.COUNTRYOFORIGIN,
                updatedCandidate.GENDER,
                updatedCandidate.LEVEL,
                updatedCandidate.EXPERTISE,
                updatedCandidate.DBLP,
                updatedCandidate.ITERATION,
                updatedCandidate.DECISION,
                id
            ],
            (err, updateResults) => {
                if (err) {
                    return res.status(500).json({ error: err.message });
                }

                console.log("Data updated:", { id, ...updatedCandidate });
                res.status(200).json(updatedCandidate);
            }
        );
    });
});


app.delete('/api/candidates/:id', (req, res) => {
    const { id } = req.params;

    const query = 'DELETE FROM Candidate_Rec WHERE ID = ?';

    pool.query(query, [id], (err, results) => {
        if (err) {
            return res.status(500).json({ error: err.message });
        }
        console.log("Candidate deleted:", { id });
        res.status(204).send();
    });
});

// Route to get data from SancusDB table
app.get('/api/sancus', (req, res) => {
    pool.query('SELECT * FROM SancusDB', (err, results) => {
        if (err) {
            return res.status(500).json({ error: err.message });
        }
        res.json(results);
    });
});

app.post('/api/sancus', (req, res) => {
    const {
        name,
        country,
        countryoforigin,
        email,
        organization,
        dblp
    } = req.body;

    const query = `
        INSERT INTO SancusDB 
        (name,country,countryoforigin,email,organization,dblp) 
        VALUES (?, ?, ?, ?, ?, ?)
    `;

    pool.query(
        query,
        [name, country, countryoforigin, email, organization, dblp],
        (err) => {
            if (err) {
                return res.status(500).json({ error: err.message });
            }
            console.log("Query Results:", req.body);
            res.status(201).json(req.body);
        }
    );
});

app.put('/api/sancus/:id', (req, res) => {
    const { id } = req.params;
    const {
        name,
        country,
        countryoforigin,
        email,
        organization,
        dblp
    } = req.body;

    const query = `
        UPDATE SancusDB
        SET name = ?, country = ?, countryoforigin = ?, email = ?, organization = ?, dblp = ?
        WHERE ID = ?
    `;

    pool.query(
        query,
        [name, country, countryoforigin, email, organization, dblp, id],
        (err, results) => {
            if (err) {
                return res.status(500).json({ error: err.message });
            }
            res.status(200).json(req.body);
        }
    );
});

app.delete('/api/sancus/:id', (req, res) => {
    const { id } = req.params;

    const query = 'DELETE FROM SancusDB WHERE ID = ?';

    pool.query(query, [id], (err, results) => {
        if (err) {
            return res.status(500).json({ error: err.message });
        }
        console.log("Candidate deleted:", { id });
        res.status(204).send();
    });
});

app.listen(port, () => {
    console.log(`Server running on http://localhost:${port}`);
});
